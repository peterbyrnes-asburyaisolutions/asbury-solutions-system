#pragma once

// Pure C++ helpers for EverOS trajectory sync (no Arduino deps).
// Used by sync_client.cpp on-device and by native unit tests.

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace SyncProtocol {

constexpr std::size_t kMaxBatchMessages = 200;
constexpr std::size_t kRagContextCap = 600;
constexpr const char* kAppId = "genesis-mini";
constexpr const char* kCursorPath = "/AOS/AGENT/.sync_cursor";
constexpr const char* kMemoryPath = "/AOS/AGENT/memory.jsonl";
constexpr int64_t kTimeValidEpochSec = 1700000000LL;  // ~2023-11-14

inline bool isValidDeviceId(const std::string& id) {
  if (id.empty() || id.size() > 128) {
    return false;
  }
  if (id == "." || id == "..") {
    return false;
  }
  for (unsigned char c : id) {
    const bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                    (c >= '0' && c <= '9') || c == '_' || c == '.' ||
                    c == '@' || c == '+' || c == '-';
    if (!ok) {
      return false;
    }
  }
  return true;
}

inline bool parseCursor(const std::string& raw, uint64_t& offset) {
  offset = 0;
  if (raw.empty()) {
    return true;
  }
  std::size_t i = 0;
  while (i < raw.size() &&
         (raw[i] == ' ' || raw[i] == '\t' || raw[i] == '\r' || raw[i] == '\n')) {
    ++i;
  }
  if (i >= raw.size()) {
    return true;
  }
  uint64_t v = 0;
  bool any = false;
  for (; i < raw.size(); ++i) {
    char c = raw[i];
    if (c >= '0' && c <= '9') {
      any = true;
      v = v * 10ULL + static_cast<uint64_t>(c - '0');
    } else if (c == ' ' || c == '\t' || c == '\r' || c == '\n') {
      break;
    } else {
      return false;
    }
  }
  if (!any) {
    return false;
  }
  offset = v;
  return true;
}

inline std::string formatCursor(uint64_t offset) {
  return std::to_string(offset) + "\n";
}

inline std::string dailySessionId(const std::string& deviceId, int64_t epochSecUtc) {
  // UTC YYYYMMDD after NTP; callers pass time(nullptr) when valid.
  const int64_t days = epochSecUtc / 86400LL;
  // Civil date from Unix day count (Howard Hinnant algorithm).
  int64_t z = days + 719468LL;
  const int64_t era = (z >= 0 ? z : z - 146096LL) / 146097LL;
  const uint32_t doe = static_cast<uint32_t>(z - era * 146097LL);
  const uint32_t yoe =
      (doe - doe / 1460U + doe / 36524U - doe / 146096U) / 365U;
  int64_t y = static_cast<int64_t>(yoe) + era * 400LL;
  const uint32_t doy = doe - (365U * yoe + yoe / 4U - yoe / 100U);
  const uint32_t mp = (5U * doy + 2U) / 153U;
  const uint32_t d = doy - (153U * mp + 2U) / 5U + 1U;
  const uint32_t m = mp < 10U ? mp + 3U : mp - 9U;
  y += (m <= 2);
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%04lld%02u%02u",
                static_cast<long long>(y), m, d);
  return deviceId + "-" + buf;
}

struct MemoryLine {
  int64_t ts = 0;
  std::string role;
  std::string text;
  bool uptimeClock = false;
  bool ok = false;
};

namespace detail {

inline void skipWs(const std::string& s, std::size_t& i) {
  while (i < s.size() &&
         (s[i] == ' ' || s[i] == '\t' || s[i] == '\r' || s[i] == '\n')) {
    ++i;
  }
}

inline bool matchLiteral(const std::string& s, std::size_t& i, const char* lit) {
  std::size_t j = 0;
  while (lit[j] != '\0') {
    if (i + j >= s.size() || s[i + j] != lit[j]) {
      return false;
    }
    ++j;
  }
  i += j;
  return true;
}

inline bool parseJsonString(const std::string& s, std::size_t& i, std::string& out) {
  out.clear();
  if (i >= s.size() || s[i] != '"') {
    return false;
  }
  ++i;
  while (i < s.size()) {
    char c = s[i++];
    if (c == '"') {
      return true;
    }
    if (c == '\\' && i < s.size()) {
      char e = s[i++];
      switch (e) {
        case '"':
        case '\\':
        case '/':
          out.push_back(e);
          break;
        case 'n':
          out.push_back('\n');
          break;
        case 'r':
          out.push_back('\r');
          break;
        case 't':
          out.push_back('\t');
          break;
        default:
          out.push_back(e);
          break;
      }
    } else {
      out.push_back(c);
    }
  }
  return false;
}

inline bool findKey(const std::string& s, const char* key, std::size_t& pos) {
  const std::string needle = std::string("\"") + key + "\"";
  std::size_t at = s.find(needle, pos);
  if (at == std::string::npos) {
    return false;
  }
  pos = at + needle.size();
  skipWs(s, pos);
  if (pos >= s.size() || s[pos] != ':') {
    return false;
  }
  ++pos;
  skipWs(s, pos);
  return true;
}

}  // namespace detail

inline MemoryLine parseMemoryLine(const std::string& jsonLine) {
  MemoryLine line;
  std::string trimmed = jsonLine;
  while (!trimmed.empty() &&
         (trimmed.back() == '\n' || trimmed.back() == '\r' ||
          trimmed.back() == ' ' || trimmed.back() == '\t')) {
    trimmed.pop_back();
  }
  if (trimmed.empty()) {
    return line;
  }

  std::size_t pos = 0;
  if (detail::findKey(trimmed, "ts", pos)) {
    bool neg = false;
    if (pos < trimmed.size() && trimmed[pos] == '-') {
      neg = true;
      ++pos;
    }
    int64_t v = 0;
    bool any = false;
    while (pos < trimmed.size() && trimmed[pos] >= '0' && trimmed[pos] <= '9') {
      any = true;
      v = v * 10 + (trimmed[pos] - '0');
      ++pos;
    }
    if (any) {
      line.ts = neg ? -v : v;
    }
  }

  pos = 0;
  if (detail::findKey(trimmed, "role", pos)) {
    detail::parseJsonString(trimmed, pos, line.role);
  }

  pos = 0;
  if (detail::findKey(trimmed, "text", pos)) {
    detail::parseJsonString(trimmed, pos, line.text);
  }

  pos = 0;
  if (detail::findKey(trimmed, "clock", pos)) {
    std::string clock;
    if (detail::parseJsonString(trimmed, pos, clock) && clock == "uptime") {
      line.uptimeClock = true;
    }
  }

  line.ok = !line.role.empty() && !line.text.empty();
  return line;
}

inline std::string jsonEscape(const std::string& in) {
  std::string out;
  out.reserve(in.size() + 8);
  for (unsigned char c : in) {
    switch (c) {
      case '"':
        out += "\\\"";
        break;
      case '\\':
        out += "\\\\";
        break;
      case '\n':
        out += "\\n";
        break;
      case '\r':
        out += "\\r";
        break;
      case '\t':
        out += "\\t";
        break;
      default:
        if (c < 0x20) {
          char buf[8];
          std::snprintf(buf, sizeof(buf), "\\u%04x", c);
          out += buf;
        } else {
          out.push_back(static_cast<char>(c));
        }
        break;
    }
  }
  return out;
}

struct SyncMessage {
  std::string senderId;
  std::string role;
  int64_t timestampMs = 0;
  std::string content;
};

inline bool shouldIncludeInBatch(const MemoryLine& line) {
  return line.ok && !line.uptimeClock;
}

inline SyncMessage toSyncMessage(const MemoryLine& line,
                                const std::string& deviceId) {
  SyncMessage m;
  m.senderId = deviceId;
  m.role = line.role;
  // memory.jsonl ts is already epoch ms when clock is wall time.
  m.timestampMs = line.ts > 0 ? line.ts : 1;
  m.content = line.text;
  return m;
}

inline std::string buildMemorizeAddJson(const std::string& sessionId,
                                        const std::string& deviceId,
                                        const std::vector<SyncMessage>& messages) {
  std::string out;
  out.reserve(256 + messages.size() * 64);
  out += "{\"session_id\":\"";
  out += jsonEscape(sessionId);
  out += "\",\"app_id\":\"";
  out += kAppId;
  out += "\",\"project_id\":\"";
  out += jsonEscape(deviceId);
  out += "\",\"messages\":[";
  for (std::size_t i = 0; i < messages.size(); ++i) {
    if (i > 0) {
      out += ',';
    }
    const SyncMessage& m = messages[i];
    out += "{\"sender_id\":\"";
    out += jsonEscape(m.senderId);
    out += "\",\"role\":\"";
    out += jsonEscape(m.role);
    out += "\",\"timestamp\":";
    out += std::to_string(m.timestampMs);
    out += ",\"content\":\"";
    out += jsonEscape(m.content);
    out += "\"}";
  }
  out += "]}";
  return out;
}

inline std::string buildSearchJson(const std::string& deviceId,
                                   const std::string& query, int topK) {
  std::string out;
  out += "{\"user_id\":\"";
  out += jsonEscape(deviceId);
  out += "\",\"app_id\":\"";
  out += kAppId;
  out += "\",\"project_id\":\"";
  out += jsonEscape(deviceId);
  out += "\",\"query\":\"";
  out += jsonEscape(query);
  out += "\",\"top_k\":";
  out += std::to_string(topK);
  out += ",\"method\":\"keyword\"}";
  return out;
}

// Extract short RAG blurbs from a search response JSON (episodes[].summary
// or atomic_facts[].content). Caps at kRagContextCap characters.
inline std::string formatRagContext(const std::string& searchResponseJson) {
  std::vector<std::string> hits;
  std::size_t pos = 0;
  while (hits.size() < 3 && pos < searchResponseJson.size()) {
    std::size_t keyPos = pos;
    std::string value;
    if (detail::findKey(searchResponseJson, "summary", keyPos) &&
        detail::parseJsonString(searchResponseJson, keyPos, value) &&
        !value.empty()) {
      hits.push_back(value);
      pos = keyPos;
      continue;
    }
    keyPos = pos;
    if (detail::findKey(searchResponseJson, "content", keyPos) &&
        detail::parseJsonString(searchResponseJson, keyPos, value) &&
        !value.empty()) {
      hits.push_back(value);
      pos = keyPos;
      continue;
    }
    break;
  }

  if (hits.empty()) {
    return "";
  }

  std::string out = "Relevant memory:\n";
  for (std::size_t i = 0; i < hits.size(); ++i) {
    std::string piece = "- " + hits[i];
    if (out.size() + piece.size() + 1 > kRagContextCap) {
      const std::size_t room =
          kRagContextCap > out.size() + 4 ? kRagContextCap - out.size() - 4 : 0;
      if (room > 8) {
        out += piece.substr(0, room);
        out += "...";
      }
      break;
    }
    out += piece;
    if (i + 1 < hits.size()) {
      out += '\n';
    }
  }
  if (out.size() > kRagContextCap) {
    out.resize(kRagContextCap);
  }
  return out;
}

inline std::string truncateForLog(const std::string& text, std::size_t maxLen = 80) {
  if (text.size() <= maxLen) {
    return text;
  }
  return text.substr(0, maxLen) + "...";
}

}  // namespace SyncProtocol
