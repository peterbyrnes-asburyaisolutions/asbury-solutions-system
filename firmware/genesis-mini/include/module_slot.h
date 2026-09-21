#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

enum class ModuleKind : uint8_t {
  None = 0,
  Panel,
  Climate,
  Ambient,
  Control,
  Unknown,
};

struct ModuleSlot {
  uint8_t port = 0;
  ModuleKind kind = ModuleKind::None;
  String profile;
  String label;
  bool present = false;
  JsonDocument config;

  void reset(uint8_t p) {
    port = p;
    kind = ModuleKind::None;
    profile = "";
    label = "";
    present = false;
    config.clear();
  }
};

namespace ModuleBus {

bool begin();
void refresh();
uint8_t countPresent();
ModuleSlot* slot(uint8_t port);  // ports 2..4
void listToSerial();
bool readPort(uint8_t port, String& out);
bool writePort(uint8_t port, const String& payload);
bool beep(uint8_t port, uint16_t ms = 80);
const char* kindName(ModuleKind k);

}  // namespace ModuleBus
