#pragma once

#include <Arduino.h>

struct LlmConfig {
  bool enabled = false;
  String baseUrl;       // e.g. https://api.openai.com/v1
  String apiKey;
  String model;
  uint32_t timeoutMs = 30000;
};

namespace LlmClient {

void configure(const LlmConfig& cfg);
bool isConfigured();
bool connectWifi(const char* ssid, const char* pass, uint32_t timeoutMs = 20000);
bool wifiConnected();

// POST /chat/completions style request. Returns assistant text in `out`.
bool chat(const String& systemPrompt,
          const String& userMessage,
          String& out,
          String* err = nullptr);

}  // namespace LlmClient
