#pragma once

#include <Arduino.h>

struct DhtReading {
  bool ok = false;
  float temperatureC = NAN;
  float humidity = NAN;
};

namespace DhtReader {

// One-shot DHT11/DHT22 read on `pin`. Tries DHT22 timing first, falls back
// to DHT11. Returns ok=false on timeout / checksum failure.
DhtReading read(uint8_t pin);

}  // namespace DhtReader
