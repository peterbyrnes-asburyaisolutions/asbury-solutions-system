#include "dht_reader.h"

namespace DhtReader {
namespace {

bool expectLevel(uint8_t pin, bool level, uint32_t timeoutUs) {
  uint32_t start = micros();
  while (digitalRead(pin) == level) {
    if ((micros() - start) > timeoutUs) {
      return false;
    }
  }
  return true;
}

DhtReading decode(const uint8_t data[5], bool dht22) {
  DhtReading r;
  uint8_t sum = static_cast<uint8_t>(data[0] + data[1] + data[2] + data[3]);
  if (sum != data[4]) {
    return r;
  }

  if (dht22) {
    int16_t rawH = (data[0] << 8) | data[1];
    int16_t rawT = (data[2] << 8) | data[3];
    r.humidity = rawH * 0.1f;
    bool neg = (rawT & 0x8000) != 0;
    rawT &= 0x7FFF;
    r.temperatureC = rawT * 0.1f;
    if (neg) {
      r.temperatureC = -r.temperatureC;
    }
  } else {
    r.humidity = data[0];
    r.temperatureC = data[2];
  }
  r.ok = true;
  return r;
}

DhtReading sample(uint8_t pin, bool dht22) {
  DhtReading fail;
  uint8_t data[5] = {0};

  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  delay(dht22 ? 2 : 20);
  digitalWrite(pin, HIGH);
  delayMicroseconds(30);
  pinMode(pin, INPUT_PULLUP);

  // Wait for sensor response: 80us low, 80us high
  if (!expectLevel(pin, HIGH, 100)) {
    return fail;
  }
  if (!expectLevel(pin, LOW, 100)) {
    return fail;
  }
  if (!expectLevel(pin, HIGH, 100)) {
    return fail;
  }

  for (int i = 0; i < 40; i++) {
    if (!expectLevel(pin, LOW, 80)) {
      return fail;
    }
    uint32_t t0 = micros();
    if (!expectLevel(pin, HIGH, 100)) {
      return fail;
    }
    uint32_t width = micros() - t0;
    data[i / 8] <<= 1;
    if (width > 40) {
      data[i / 8] |= 1;
    }
  }

  return decode(data, dht22);
}

}  // namespace

DhtReading read(uint8_t pin) {
  DhtReading r = sample(pin, true);
  if (r.ok) {
    return r;
  }
  delay(50);
  return sample(pin, false);
}

}  // namespace DhtReader
