#include "module_slot.h"

#include "board_pins.h"
#include "dht_reader.h"
#include "sd_store.h"

#include <ArduinoJson.h>
#include <cstring>

namespace ModuleBus {
namespace {

ModuleSlot slots[3];  // ports 2,3,4

ModuleKind parseKind(const char* s) {
  if (s == nullptr) {
    return ModuleKind::None;
  }
  if (strcasecmp(s, "panel") == 0) return ModuleKind::Panel;
  if (strcasecmp(s, "climate") == 0) return ModuleKind::Climate;
  if (strcasecmp(s, "ambient") == 0) return ModuleKind::Ambient;
  if (strcasecmp(s, "control") == 0) return ModuleKind::Control;
  return ModuleKind::Unknown;
}

int indexForPort(uint8_t port) {
  if (port < AX22_FIRST_MODULE_PORT || port > AX22_LAST_MODULE_PORT) {
    return -1;
  }
  return port - AX22_FIRST_MODULE_PORT;
}

bool loadPortConfig(uint8_t port, ModuleSlot& slot) {
  char path[48];
  snprintf(path, sizeof(path), "/AOS/MODULES/port%u.json", port);
  String raw;
  if (!SdStore::readFile(path, raw)) {
    slot.present = false;
    slot.kind = ModuleKind::None;
    slot.profile = "";
    slot.label = "";
    return false;
  }

  DeserializationError err = deserializeJson(slot.config, raw);
  if (err) {
    Serial.printf("[modules] port%u JSON error: %s\n", port, err.c_str());
    slot.present = false;
    return false;
  }

  const char* profile = slot.config["profile"] | "unknown";
  const char* kindStr = slot.config["kind"] | profile;
  slot.profile = profile;
  slot.kind = parseKind(kindStr);
  slot.label = slot.config["label"] | profile;
  slot.present = slot.config["enabled"] | true;

  // Merge profile defaults when available
  char profilePath[64];
  snprintf(profilePath, sizeof(profilePath), "/AOS/MODULES/profiles/%s.json",
           profile);
  String profileRaw;
  if (SdStore::readFile(profilePath, profileRaw)) {
    JsonDocument profileDoc;
    if (!deserializeJson(profileDoc, profileRaw)) {
      for (JsonPair kv : profileDoc.as<JsonObject>()) {
        if (!slot.config.containsKey(kv.key())) {
          slot.config[kv.key()] = kv.value();
        }
      }
      if (slot.kind == ModuleKind::None || slot.kind == ModuleKind::Unknown) {
        slot.kind = parseKind(profileDoc["kind"] | profile);
      }
    }
  }

  const Ax22PortPins* pins = ax22PinsForPort(port);
  if (pins != nullptr) {
    pinMode(pins->a, INPUT_PULLUP);
    pinMode(pins->b, OUTPUT);
    digitalWrite(pins->b, LOW);
    pinMode(pins->c, INPUT);
  }
  return true;
}

}  // namespace

const char* kindName(ModuleKind k) {
  switch (k) {
    case ModuleKind::None: return "none";
    case ModuleKind::Panel: return "panel";
    case ModuleKind::Climate: return "climate";
    case ModuleKind::Ambient: return "ambient";
    case ModuleKind::Control: return "control";
    case ModuleKind::Unknown: return "unknown";
    default: {
      ModuleKind unreachable = k;
      (void)unreachable;
      return "?";
    }
  }
}

bool begin() {
  for (uint8_t p = AX22_FIRST_MODULE_PORT; p <= AX22_LAST_MODULE_PORT; p++) {
    int idx = indexForPort(p);
    slots[idx] = ModuleSlot{};
    slots[idx].port = p;
  }
  refresh();
  return true;
}

void refresh() {
  for (uint8_t p = AX22_FIRST_MODULE_PORT; p <= AX22_LAST_MODULE_PORT; p++) {
    int idx = indexForPort(p);
    loadPortConfig(p, slots[idx]);
  }
}

uint8_t countPresent() {
  uint8_t n = 0;
  for (auto& s : slots) {
    if (s.present) {
      n++;
    }
  }
  return n;
}

ModuleSlot* slot(uint8_t port) {
  int idx = indexForPort(port);
  if (idx < 0) {
    return nullptr;
  }
  return &slots[idx];
}

void listToSerial() {
  Serial.println(F("port  kind      profile     label"));
  for (auto& s : slots) {
    Serial.printf("  %u   %-8s  %-10s  %s%s\n", s.port, kindName(s.kind),
                  s.profile.c_str(), s.label.c_str(),
                  s.present ? "" : " (disabled)");
  }
}

bool readPort(uint8_t port, String& out) {
  ModuleSlot* s = slot(port);
  const Ax22PortPins* pins = ax22PinsForPort(port);
  if (s == nullptr || pins == nullptr) {
    out = "invalid port";
    return false;
  }
  if (!s->present) {
    out = "port empty/disabled";
    return false;
  }

  JsonDocument doc;
  doc["port"] = port;
  doc["kind"] = kindName(s->kind);
  doc["profile"] = s->profile;

  switch (s->kind) {
    case ModuleKind::Climate: {
      DhtReading r = DhtReader::read(pins->a);
      doc["ok"] = r.ok;
      if (r.ok) {
        doc["temp_c"] = r.temperatureC;
        doc["humidity"] = r.humidity;
      } else {
        doc["error"] = "dht_read_failed";
      }
      break;
    }
    case ModuleKind::Ambient: {
      int raw = analogRead(pins->c);
      doc["adc"] = raw;
      doc["lux_approx"] = map(raw, 0, 4095, 0, 1000);
      doc["digital"] = digitalRead(pins->a);
      break;
    }
    case ModuleKind::Panel: {
      doc["btn_a"] = digitalRead(pins->a) == LOW;
      doc["btn_b"] = digitalRead(pins->c) == LOW;
      break;
    }
    case ModuleKind::Control: {
      doc["state"] = digitalRead(pins->b);
      doc["sense"] = digitalRead(pins->a);
      break;
    }
    case ModuleKind::None:
    case ModuleKind::Unknown:
    default: {
      doc["gpio_a"] = digitalRead(pins->a);
      doc["gpio_b"] = digitalRead(pins->b);
      doc["gpio_c"] = analogRead(pins->c);
      break;
    }
  }

  out = "";
  serializeJson(doc, out);
  return true;
}

bool writePort(uint8_t port, const String& payload) {
  ModuleSlot* s = slot(port);
  const Ax22PortPins* pins = ax22PinsForPort(port);
  if (s == nullptr || pins == nullptr || !s->present) {
    return false;
  }

  String cmd = payload;
  cmd.trim();
  cmd.toLowerCase();

  if (cmd == "on" || cmd == "1" || cmd == "high") {
    digitalWrite(pins->b, HIGH);
    return true;
  }
  if (cmd == "off" || cmd == "0" || cmd == "low") {
    digitalWrite(pins->b, LOW);
    return true;
  }
  if (cmd == "toggle") {
    digitalWrite(pins->b, digitalRead(pins->b) == HIGH ? LOW : HIGH);
    return true;
  }

  // Optional JSON: {"pin":"b","value":1} or {"pwm":128}
  JsonDocument doc;
  if (!deserializeJson(doc, payload)) {
    if (doc.containsKey("pwm")) {
      analogWrite(pins->b, constrain(static_cast<int>(doc["pwm"]), 0, 255));
      return true;
    }
    const char* pinName = doc["pin"] | "b";
    int value = doc["value"] | 0;
    uint8_t gpio = pins->b;
    if (pinName[0] == 'a') gpio = pins->a;
    if (pinName[0] == 'c') gpio = pins->c;
    pinMode(gpio, OUTPUT);
    digitalWrite(gpio, value ? HIGH : LOW);
    return true;
  }

  Serial.printf("[modules] write parse failed: %s\n", payload.c_str());
  return false;
}

bool beep(uint8_t port, uint16_t ms) {
  const Ax22PortPins* pins = ax22PinsForPort(port);
  if (pins == nullptr) {
    return false;
  }
  pinMode(pins->b, OUTPUT);
  // Soft square buzz on pin b
  uint32_t end = millis() + ms;
  while (millis() < end) {
    digitalWrite(pins->b, HIGH);
    delayMicroseconds(500);
    digitalWrite(pins->b, LOW);
    delayMicroseconds(500);
  }
  return true;
}

}  // namespace ModuleBus
