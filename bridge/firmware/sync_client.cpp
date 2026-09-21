#include "sync_client.h"

#include "sync_protocol.h"

#include "sd_store.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

// Embedded via board_build.embed_files = data/cert/x509_crt_bundle.bin
extern const uint8_t rootca_crt_bundle_start[] asm(
    "_binary_data_cert_x509_crt_bundle_bin_start");

namespace SyncClient {
namespace {

SyncConfig gConfig;
bool searchUnreachableLogged = false;

void applyTls(WiFiClientSecure& client) {
  if (gConfig.tlsInsecure) {
    client.setInsecure();
    return;
  }
  client.setCACertBundle(rootca_crt_bundle_start);
}

String joinUrl(const String& base, const char* path) {
  String url = base;
  while (url.endsWith("/")) {
    url.remove(url.length() - 1);
  }
  if (path[0] != '/') {
    url += '/';
  }
  url += path;
  return url;
}

bool isHttpsUrl(const String& url) {
  return url.startsWith("https://") || url.startsWith("HTTPS://");
}

uint64_t loadCursor() {
  String raw;
  if (!SdStore::readFile(SyncProtocol::kCursorPath, raw)) {
    return 0;
  }
  uint64_t offset = 0;
  if (!SyncProtocol::parseCursor(raw.c_str(), offset)) {
    Serial.println(F("[sync] bad cursor — resetting to 0"));
    return 0;
  }
  return offset;
}

bool saveCursor(uint64_t offset) {
  const std::string formatted = SyncProtocol::formatCursor(offset);
  return SdStore::writeFile(SyncProtocol::kCursorPath, formatted.c_str());
}

bool postJson(const String& path, const String& payload, uint32_t timeoutMs,
              int& codeOut, String& respOut, String* err) {
  codeOut = 0;
  respOut = "";
  if (!WiFi.isConnected()) {
    if (err) *err = "wifi not connected";
    return false;
  }

  const String url = joinUrl(gConfig.baseUrl, path.c_str());

  HTTPClient http;
  http.setTimeout(timeoutMs);
  http.setConnectTimeout(timeoutMs);

  bool began = false;
  WiFiClient plain;
  WiFiClientSecure secure;
  if (isHttpsUrl(url)) {
    applyTls(secure);
    began = http.begin(secure, url);
  } else {
    began = http.begin(plain, url);
  }
  if (!began) {
    if (err) *err = "http begin failed";
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  if (gConfig.apiKey.length() > 0) {
    http.addHeader("Authorization", String("Bearer ") + gConfig.apiKey);
  }

  codeOut = http.POST(payload);
  respOut = http.getString();
  http.end();
  return true;
}

bool wallClockReady(int64_t& epochSec) {
  time_t now = time(nullptr);
  if (now > SyncProtocol::kTimeValidEpochSec) {
    epochSec = static_cast<int64_t>(now);
    return true;
  }
  return false;
}

}  // namespace

void configure(const SyncConfig& cfg) {
  gConfig = cfg;
  searchUnreachableLogged = false;
}

bool enabled() { return gConfig.enabled; }

uint32_t intervalS() { return gConfig.intervalS == 0 ? 300 : gConfig.intervalS; }

const SyncConfig& config() { return gConfig; }

bool isConfigured() {
  if (!gConfig.enabled || gConfig.baseUrl.length() == 0 ||
      gConfig.deviceId.length() == 0) {
    return false;
  }
  return SyncProtocol::isValidDeviceId(gConfig.deviceId.c_str());
}

bool syncNow(String* err) {
  if (!isConfigured()) {
    if (err) *err = "sync not configured";
    return false;
  }
  if (!SdStore::isMounted()) {
    if (err) *err = "sd not mounted";
    return false;
  }

  uint64_t cursor = loadCursor();
  const size_t fileBytes = SdStore::fileSize(SyncProtocol::kMemoryPath);
  if (cursor > fileBytes) {
    Serial.printf("[sync] cursor %llu past eof %u — clamping\n",
                  static_cast<unsigned long long>(cursor),
                  static_cast<unsigned>(fileBytes));
    cursor = fileBytes;
    saveCursor(cursor);
  }
  if (cursor >= fileBytes) {
    Serial.println(F("[sync] up to date"));
    return true;
  }

  std::vector<SyncProtocol::SyncMessage> messages;
  messages.reserve(32);
  uint64_t readOffset = cursor;
  uint64_t consumedOffset = cursor;
  String line;

  while (messages.size() < SyncProtocol::kMaxBatchMessages) {
    size_t off = static_cast<size_t>(readOffset);
    if (!SdStore::readLineAt(SyncProtocol::kMemoryPath, off, line)) {
      break;
    }
    readOffset = off;
    consumedOffset = readOffset;

    const SyncProtocol::MemoryLine parsed =
        SyncProtocol::parseMemoryLine(line.c_str());
    if (!SyncProtocol::shouldIncludeInBatch(parsed)) {
      continue;
    }
    messages.push_back(
        SyncProtocol::toSyncMessage(parsed, gConfig.deviceId.c_str()));
  }

  if (messages.empty()) {
    // Only uptime / blank lines — advance cursor without POST.
    if (consumedOffset > cursor) {
      saveCursor(consumedOffset);
      Serial.printf("[sync] advanced cursor past %u skipped bytes\n",
                    static_cast<unsigned>(consumedOffset - cursor));
    }
    return true;
  }

  int64_t epochSec = 0;
  if (!wallClockReady(epochSec)) {
    // Fall back to a stable session bucket from first message ms.
    epochSec = messages.front().timestampMs / 1000;
    if (epochSec < SyncProtocol::kTimeValidEpochSec) {
      epochSec = SyncProtocol::kTimeValidEpochSec;
    }
  }
  const std::string sessionId =
      SyncProtocol::dailySessionId(gConfig.deviceId.c_str(), epochSec);
  const std::string payloadStd = SyncProtocol::buildMemorizeAddJson(
      sessionId, gConfig.deviceId.c_str(), messages);
  const String payload = payloadStd.c_str();

  Serial.printf("[sync] posting %u msgs session=%s content0=\"%s\"\n",
                static_cast<unsigned>(messages.size()), sessionId.c_str(),
                SyncProtocol::truncateForLog(messages.front().content).c_str());

  int code = 0;
  String resp;
  if (!postJson("/api/v1/memory/add", payload, 8000, code, resp, err)) {
    return false;
  }
  if (code < 200 || code >= 300) {
    if (err) {
      *err = "http " + String(code) + ": " + resp.substring(0, 160);
    }
    Serial.printf("[sync] add failed http %d\n", code);
    return false;
  }

  if (!saveCursor(consumedOffset)) {
    if (err) *err = "cursor save failed";
    return false;
  }
  Serial.printf("[sync] ok cursor=%llu\n",
                static_cast<unsigned long long>(consumedOffset));
  return true;
}

bool syncAll(uint8_t maxBatches, String* err) {
  for (uint8_t i = 0; i < maxBatches; ++i) {
    const uint64_t before = loadCursor();
    const size_t fileBytes = SdStore::fileSize(SyncProtocol::kMemoryPath);
    if (before >= fileBytes) {
      return true;
    }
    if (!syncNow(err)) {
      return false;
    }
    const uint64_t after = loadCursor();
    if (after <= before) {
      break;
    }
  }
  return true;
}

bool search(const String& query, String& contextOut, String* err) {
  contextOut = "";
  if (!isConfigured()) {
    if (err) *err = "sync not configured";
    return false;
  }

  const std::string body = SyncProtocol::buildSearchJson(
      gConfig.deviceId.c_str(), query.c_str(), 3);
  int code = 0;
  String resp;
  // Keep RAG snappy so ask() never blocks the REPL long.
  if (!postJson("/api/v1/memory/search", String(body.c_str()), 2500, code, resp,
                err)) {
    if (!searchUnreachableLogged) {
      Serial.println(F("[sync] search unreachable — answering without memory"));
      searchUnreachableLogged = true;
    }
    return false;
  }
  if (code < 200 || code >= 300) {
    if (err) {
      *err = "http " + String(code) + ": " + resp.substring(0, 120);
    }
    if (!searchUnreachableLogged) {
      Serial.printf("[sync] search http %d — answering without memory\n", code);
      searchUnreachableLogged = true;
    }
    return false;
  }

  searchUnreachableLogged = false;
  contextOut = SyncProtocol::formatRagContext(resp.c_str()).c_str();
  return true;
}

}  // namespace SyncClient
