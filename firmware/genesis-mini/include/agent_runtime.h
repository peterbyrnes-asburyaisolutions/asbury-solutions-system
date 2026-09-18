#pragma once

#include <Arduino.h>

namespace AgentRuntime {

bool begin();
bool loadManifest();
bool loadPersonality();
const String& agentName();
const String& agentVersion();
bool localFirst();
bool llmEnabled();

// Append a memory line to /AOS/AGENT/memory.jsonl
bool remember(const char* role, const String& text);

// Run local tools first; optionally escalate to LLM when enabled.
String ask(const String& question);

void printStatus();

}  // namespace AgentRuntime
