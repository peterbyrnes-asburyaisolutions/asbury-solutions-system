#include "agent_runtime.h"

#include "llm_client.h"
#include "module_slot.h"
#include "sd_store.h"
#include "status_led.h"
#include "sync_client.h"

#include <ArduinoJson.h>
#include <WiFi.h>
#include <time.h>

namespace AgentRuntime {
namespace {

String name_ = "genesis";
String version_ = "0.2.0";
bool localFirst_ = true;
bool llmEnabled_ = false;
String personality_;
String wifiSsid_;
String wifiPass_;
LlmConfig llmCfg_;
SyncConfig syncCfg_;

String lower(const String& s) {
  String o = s;
  o.toLowerCase();
  return o;
}

bool tryLocalTool(const String& question, String& answer) {
  String q = lower(question);
  q.trim();

  if (q == "help" || q.startsWith("what can you") || q.indexOf("commands") >= 0) {
    answer =
        "Local tools: status, modules, read <port>, temperature/climate, "
        "memory note. LLM used when enabled and local tools miss.";
    return true;
  }

  if (q.indexOf("status") >= 0 || q.indexOf("who are you") >= 0) {
    answer = "I am " + name_ + " v" + version_ + " (AOS local-first=" +
             String(localFirst_ ? "true" : "false") + ", modules=" +
             String(ModuleBus::countPresent()) + ").";
    return true;
  }

  if (q.indexOf("module") >= 0 || q.indexOf("ports") >= 0) {
    answer = "Present modules: " + String(ModuleBus::countPresent()) +
             ". Use serial `modules` for detail.";
    return true;
  }

  if (q.indexOf("temp") >= 0 || q.indexOf("humid") >= 0 ||
      q.indexOf("climate") >= 0) {
    for (uint8_t p = 2; p <= 4; p++) {
      ModuleSlot* s = ModuleBus::slot(p);
      if (s && s->present && s->kind == ModuleKind::Climate) {
        String raw;
        if (ModuleBus::readPort(p, raw)) {
          answer = raw;
          return true;
        }
      }
    }
    answer = "No climate module found on ports 2-4.";
    return true;
  }

  if (q.startsWith("remember ") || q.startsWith("note ")) {
    String note = question.substring(q.startsWith("remember ") ? 9 : 5);
    note.trim();
    if (remember("user", note)) {
      answer = "Noted.";
      return true;
    }
    answer = "Failed to write memory.";
    return true;
  }

  // Explicit local read: "read 3"
  if (q.startsWith("read ")) {
    int port = q.substring(5).toInt();
    String raw;
    if (ModuleBus::readPort(static_cast<uint8_t>(port), raw)) {
      answer = raw;
      return true;
    }
    answer = "Read failed for port " + String(port);
    return true;
  }

  return false;
}

void startNtpIfNeeded() {
  if (!LlmClient::wifiConnected()) {
    return;
  }
  configTime(0, 0, "pool.ntp.org");
  Serial.println(F("[time] SNTP started (pool.ntp.org, UTC)"));
}

}  // namespace

bool begin() {
  if (!loadManifest()) {
    Serial.println(F("[agent] manifest missing — using defaults"));
  }
  loadPersonality();

  if (wifiSsid_.length() > 0) {
    StatusLed::setPattern(StatusLed::Pattern::Wifi);
    LlmClient::connectWifi(wifiSsid_.c_str(), wifiPass_.c_str());
    startNtpIfNeeded();
  }
  LlmClient::configure(llmCfg_);
  SyncClient::configure(syncCfg_);
  return true;
}

bool loadManifest() {
  String raw;
  if (!SdStore::readFile("/AOS/AGENT/manifest.json", raw)) {
    return false;
  }

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, raw);
  if (err) {
    Serial.printf("[agent] manifest JSON error: %s\n", err.c_str());
    return false;
  }

  name_ = doc["name"] | "genesis";
  version_ = doc["version"] | "0.2.0";
  localFirst_ = doc["local_first"] | true;

  wifiSsid_ = doc["wifi"]["ssid"] | "";
  wifiPass_ = doc["wifi"]["pass"] | "";

  llmCfg_.enabled = doc["llm"]["enabled"] | false;
  llmCfg_.baseUrl = doc["llm"]["base_url"] | "";
  llmCfg_.apiKey = doc["llm"]["api_key"] | "";
  llmCfg_.model = doc["llm"]["model"] | "gpt-4o-mini";
  llmCfg_.timeoutMs = doc["llm"]["timeout_ms"] | 30000;
  llmCfg_.tlsInsecure = doc["llm"]["tls_insecure"] | false;
  llmEnabled_ = llmCfg_.enabled;

  syncCfg_.enabled = doc["sync"]["enabled"] | false;
  syncCfg_.baseUrl = doc["sync"]["base_url"] | "";
  syncCfg_.apiKey = doc["sync"]["api_key"] | "";
  syncCfg_.deviceId = doc["sync"]["device_id"] | "";
  syncCfg_.intervalS = doc["sync"]["interval_s"] | 300;
  syncCfg_.tlsInsecure = doc["sync"]["tls_insecure"] | false;

  Serial.printf("[agent] loaded %s v%s local_first=%d llm=%d sync=%d\n",
                name_.c_str(), version_.c_str(), localFirst_, llmEnabled_,
                syncCfg_.enabled);
  return true;
}

bool loadPersonality() {
  personality_ = "";
  if (!SdStore::readFile("/AOS/AGENT/personality.txt", personality_)) {
    personality_ =
        "You are the on-device agent for Axiometa Genesis Mini. Be concise.";
    return false;
  }
  personality_.trim();
  return true;
}

const String& agentName() { return name_; }
const String& agentVersion() { return version_; }
bool localFirst() { return localFirst_; }
bool llmEnabled() { return llmEnabled_; }

bool remember(const char* role, const String& text) {
  if (role == nullptr) {
    return false;
  }
  JsonDocument doc;
  const time_t now = time(nullptr);
  if (now > 1700000000) {
    doc["ts"] = static_cast<uint64_t>(now) * 1000ULL;
  } else {
    doc["ts"] = millis();
    doc["clock"] = "uptime";
  }
  doc["role"] = role;
  doc["text"] = text;
  String line;
  serializeJson(doc, line);
  line += '\n';
  return SdStore::appendFile("/AOS/AGENT/memory.jsonl", line.c_str());
}

String ask(const String& question) {
  remember("user", question);

  String answer;
  bool handled = false;

  if (localFirst_) {
    handled = tryLocalTool(question, answer);
  }

  if (!handled && llmEnabled_ && LlmClient::isConfigured()) {
    StatusLed::setPattern(StatusLed::Pattern::Thinking);
    String err;
    if (LlmClient::chat(personality_, question, answer, &err)) {
      handled = true;
    } else {
      answer = String("LLM error: ") + err;
      handled = true;
    }
    StatusLed::setPattern(StatusLed::Pattern::Ready);
  }

  if (!handled) {
    // Local-last fallback if local_first was false
    if (!localFirst_ && tryLocalTool(question, answer)) {
      handled = true;
    }
  }

  if (!handled) {
    answer =
        "No local tool matched and LLM is disabled. Try: status, modules, "
        "read <n>, or enable llm in manifest.json.";
  }

  remember("assistant", answer);
  return answer;
}

void printStatus() {
  Serial.println(F("--- agent status ---"));
  Serial.printf("name: %s\n", name_.c_str());
  Serial.printf("version: %s\n", version_.c_str());
  Serial.printf("local_first: %s\n", localFirst_ ? "true" : "false");
  Serial.printf("llm.enabled: %s\n", llmEnabled_ ? "true" : "false");
  Serial.printf("llm.model: %s\n", llmCfg_.model.c_str());
  Serial.printf("sync.enabled: %s\n", syncCfg_.enabled ? "true" : "false");
  Serial.printf("sync.device_id: %s\n", syncCfg_.deviceId.c_str());
  Serial.printf("sync.interval_s: %u\n",
                static_cast<unsigned>(SyncClient::intervalS()));
  Serial.printf("wifi: %s\n",
                LlmClient::wifiConnected()
                    ? WiFi.localIP().toString().c_str()
                    : "disconnected");
  const time_t now = time(nullptr);
  if (now > 1700000000) {
    Serial.printf("time: %ld (epoch)\n", static_cast<long>(now));
  } else {
    Serial.println(F("time: not set (uptime clock)"));
  }
  Serial.printf("modules: %u\n", ModuleBus::countPresent());
  Serial.printf("memory.jsonl: %u bytes\n",
                static_cast<unsigned>(SdStore::fileSize("/AOS/AGENT/memory.jsonl")));
}

}  // namespace AgentRuntime
