#pragma once

#include <Arduino.h>

struct SyncConfig {
  bool enabled = false;
  String baseUrl;     // EverOS base, e.g. http://192.168.1.10:8000
  String apiKey;      // bearer token (never logged)
  String deviceId;    // must match ^[a-zA-Z0-9_.@+-]+$
  uint32_t intervalS = 300;
  bool tlsInsecure = false;
};

namespace SyncClient {

void configure(const SyncConfig& cfg);
bool isConfigured();
bool enabled();
uint32_t intervalS();
const SyncConfig& config();

// Upload pending memory.jsonl lines (batches of <=200). Advances
// /AOS/AGENT/.sync_cursor only on HTTP 2xx. Returns true if caught up
// or nothing to send; false on transport / HTTP failure.
bool syncNow(String* err = nullptr);

// Drain pending lines (multiple batches). maxBatches caps work per call.
bool syncAll(uint8_t maxBatches = 32, String* err = nullptr);

// POST /api/v1/memory/search — fills contextOut with "Relevant memory:"
// block (may be empty). Short timeout; never throws. Returns false if
// unreachable (caller should answer without context).
bool search(const String& query, String& contextOut, String* err = nullptr);

}  // namespace SyncClient
