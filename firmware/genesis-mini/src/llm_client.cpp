#include "llm_client.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

namespace LlmClient {
namespace {

LlmConfig config;
bool wifiOk = false;

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

}  // namespace

void configure(const LlmConfig& cfg) { config = cfg; }

bool isConfigured() {
  return config.enabled && config.baseUrl.length() > 0 &&
         config.apiKey.length() > 0 && config.model.length() > 0;
}

bool connectWifi(const char* ssid, const char* pass, uint32_t timeoutMs) {
  if (ssid == nullptr || ssid[0] == '\0') {
    wifiOk = false;
    return false;
  }
  if (WiFi.status() == WL_CONNECTED) {
    wifiOk = true;
    return true;
  }

  Serial.printf("[wifi] connecting to %s ...\n", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, pass ? pass : "");

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < timeoutMs) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();

  wifiOk = WiFi.status() == WL_CONNECTED;
  if (wifiOk) {
    Serial.printf("[wifi] ok ip=%s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println(F("[wifi] failed"));
  }
  return wifiOk;
}

bool wifiConnected() { return WiFi.status() == WL_CONNECTED; }

bool chat(const String& systemPrompt, const String& userMessage, String& out,
          String* err) {
  out = "";
  if (!isConfigured()) {
    if (err) *err = "llm not configured";
    return false;
  }
  if (!wifiConnected()) {
    if (err) *err = "wifi not connected";
    return false;
  }

  JsonDocument body;
  body["model"] = config.model;
  JsonArray messages = body["messages"].to<JsonArray>();
  if (systemPrompt.length() > 0) {
    JsonObject sys = messages.add<JsonObject>();
    sys["role"] = "system";
    sys["content"] = systemPrompt;
  }
  JsonObject user = messages.add<JsonObject>();
  user["role"] = "user";
  user["content"] = userMessage;
  body["temperature"] = 0.3;

  String payload;
  serializeJson(body, payload);

  String url = joinUrl(config.baseUrl, "/chat/completions");

  WiFiClientSecure client;
  // Phase 0: insecure TLS. Proper CA bundle lands in a later phase.
  client.setInsecure();

  HTTPClient http;
  http.setTimeout(config.timeoutMs);
  if (!http.begin(client, url)) {
    if (err) *err = "http begin failed";
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + config.apiKey);

  int code = http.POST(payload);
  String resp = http.getString();
  http.end();

  if (code < 200 || code >= 300) {
    if (err) {
      *err = "http " + String(code) + ": " + resp.substring(0, 160);
    }
    return false;
  }

  JsonDocument doc;
  DeserializationError jerr = deserializeJson(doc, resp);
  if (jerr) {
    if (err) *err = String("json: ") + jerr.c_str();
    return false;
  }

  const char* content = doc["choices"][0]["message"]["content"];
  if (content == nullptr) {
    if (err) *err = "missing content";
    return false;
  }
  out = content;
  return true;
}

}  // namespace LlmClient
