#include <Arduino.h>

#include "agent_runtime.h"
#include "board_pins.h"
#include "module_slot.h"
#include "oled_ssd1306.h"
#include "sd_store.h"
#include "status_led.h"

#ifndef AOS_VERSION
#define AOS_VERSION "0.2.0"
#endif

namespace {

String lineBuf;

void printBanner() {
  Serial.println();
  Serial.println(F("========================================"));
  Serial.println(F("  Axiometa Genesis Mini"));
  Serial.print(F("  Agentic Operating System v"));
  Serial.println(AOS_VERSION);
  Serial.println(F("========================================"));
}

void printHelp() {
  Serial.println(F("Commands:"));
  Serial.println(F("  help                 show this help"));
  Serial.println(F("  status               agent + system status"));
  Serial.println(F("  modules              list AX22 module slots"));
  Serial.println(F("  read <N>             read module on port N (2-4)"));
  Serial.println(F("  write <N> <payload>  write to module port N"));
  Serial.println(F("  beep <N>             beep / buzz on port N"));
  Serial.println(F("  ask <question>       ask the on-device agent"));
  Serial.println(F("  install              list /AOS/INSTALL (Phase 0 stub)"));
}

void cmdStatus() {
  Serial.println(F("--- system ---"));
  Serial.printf("aos: %s\n", AOS_VERSION);
  Serial.printf("sd: %s\n", SdStore::isMounted() ? "mounted" : "absent");
  Serial.printf("free heap: %u\n", ESP.getFreeHeap());
  Serial.printf("psram: %u\n", ESP.getPsramSize());
  AgentRuntime::printStatus();
}

void cmdInstall() {
  Serial.println(F("[install] Phase 0 stub — drop packages under /AOS/INSTALL"));
  Serial.println(F("Bridge/sync install pipeline arrives in Phase 3."));
  if (!SdStore::isMounted()) {
    Serial.println(F("[install] SD not mounted"));
    return;
  }
  if (!SdStore::exists("/AOS/INSTALL")) {
    Serial.println(F("[install] /AOS/INSTALL missing"));
    return;
  }
  Serial.println(F("[install] directory present (host tools prepare packages)"));
}

void handleLine(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  String lower = line;
  lower.toLowerCase();

  if (lower == "help" || lower == "?") {
    printHelp();
    return;
  }
  if (lower == "status") {
    cmdStatus();
    return;
  }
  if (lower == "modules") {
    ModuleBus::refresh();
    ModuleBus::listToSerial();
    return;
  }
  if (lower == "install") {
    cmdInstall();
    return;
  }

  if (lower.startsWith("read ")) {
    int port = lower.substring(5).toInt();
    String out;
    if (ModuleBus::readPort(static_cast<uint8_t>(port), out)) {
      Serial.println(out);
    } else {
      Serial.printf("read failed: %s\n", out.c_str());
    }
    return;
  }

  if (lower.startsWith("write ")) {
    // write N payload...
    int sp = line.indexOf(' ', 6);
    if (sp < 0) {
      Serial.println(F("usage: write <N> <payload>"));
      return;
    }
    int port = line.substring(6, sp).toInt();
    String payload = line.substring(sp + 1);
    payload.trim();
    if (ModuleBus::writePort(static_cast<uint8_t>(port), payload)) {
      Serial.println(F("ok"));
    } else {
      Serial.println(F("write failed"));
    }
    return;
  }

  if (lower.startsWith("beep ")) {
    int port = lower.substring(5).toInt();
    if (ModuleBus::beep(static_cast<uint8_t>(port))) {
      Serial.println(F("beep ok"));
    } else {
      Serial.println(F("beep failed"));
    }
    return;
  }

  if (lower.startsWith("ask ")) {
    String q = line.substring(4);
    q.trim();
    StatusLed::setPattern(StatusLed::Pattern::Busy);
    String answer = AgentRuntime::ask(q);
    StatusLed::setPattern(StatusLed::Pattern::Ready);
    Serial.print(F("agent> "));
    Serial.println(answer);
    Oled::showStatus("ask", answer.substring(0, 21).c_str());
    return;
  }

  Serial.println(F("unknown command — try `help`"));
}

void pollSerial() {
  while (Serial.available()) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      handleLine(lineBuf);
      lineBuf = "";
      Serial.print(F("aos> "));
      continue;
    }
    if (lineBuf.length() < 300) {
      lineBuf += c;
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(800);
  printBanner();

  StatusLed::begin();
  pinMode(PIN_BUTTON, INPUT_PULLUP);

  Oled::begin();
  Oled::showBanner(AOS_VERSION);

  if (!SdStore::begin()) {
    StatusLed::setPattern(StatusLed::Pattern::Error);
    Serial.println(F("[boot] continuing without SD — insert card & reset"));
  } else {
    ModuleBus::begin();
    AgentRuntime::begin();
    StatusLed::setPattern(StatusLed::Pattern::Ready);
    Oled::showStatus(AgentRuntime::agentName().c_str(), "ready");
  }

  printHelp();
  Serial.print(F("aos> "));
}

void loop() {
  StatusLed::tick();
  pollSerial();

  static uint32_t lastBtn = 0;
  if (digitalRead(PIN_BUTTON) == LOW && millis() - lastBtn > 400) {
    lastBtn = millis();
    Serial.println(F("\n[button] status"));
    cmdStatus();
    Serial.print(F("aos> "));
  }
}
