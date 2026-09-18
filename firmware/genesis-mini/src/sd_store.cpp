#include "sd_store.h"

#include "board_pins.h"

#include <SPI.h>
#include <SdFat.h>

namespace SdStore {
namespace {

SdFat sd;
bool mounted = false;

String parentDir(const char* path) {
  String p(path);
  int slash = p.lastIndexOf('/');
  if (slash <= 0) {
    return String("/");
  }
  return p.substring(0, slash);
}

}  // namespace

bool begin() {
  if (mounted) {
    return true;
  }

  SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, PIN_SD_CS);

  // 16 MHz is a safe default for modular SD adapters on short AX22 runs.
  if (!sd.begin(SdSpiConfig(PIN_SD_CS, SHARED_SPI, SD_SCK_MHZ(16)))) {
    Serial.println(F("[sd] mount failed"));
    mounted = false;
    return false;
  }

  mounted = true;
  Serial.println(F("[sd] mounted"));
  ensureLayout();
  return true;
}

bool isMounted() { return mounted; }

void end() {
  if (mounted) {
    sd.end();
    mounted = false;
  }
}

bool exists(const char* path) {
  if (!mounted || path == nullptr) {
    return false;
  }
  return sd.exists(path);
}

bool mkdirRecursive(const char* path) {
  if (!mounted || path == nullptr || path[0] == '\0') {
    return false;
  }
  if (sd.exists(path)) {
    return true;
  }
  return sd.mkdir(path, true);
}

bool readFile(const char* path, String& out) {
  out = "";
  if (!mounted || path == nullptr) {
    return false;
  }
  FsFile f = sd.open(path, O_RDONLY);
  if (!f) {
    return false;
  }
  while (f.available()) {
    out += static_cast<char>(f.read());
  }
  f.close();
  return true;
}

bool writeFile(const char* path, const char* data) {
  if (!mounted || path == nullptr || data == nullptr) {
    return false;
  }
  String dir = parentDir(path);
  if (dir.length() > 1) {
    mkdirRecursive(dir.c_str());
  }
  FsFile f = sd.open(path, O_WRONLY | O_CREAT | O_TRUNC);
  if (!f) {
    return false;
  }
  size_t n = strlen(data);
  size_t w = f.write(reinterpret_cast<const uint8_t*>(data), n);
  f.close();
  return w == n;
}

bool appendFile(const char* path, const char* data) {
  if (!mounted || path == nullptr || data == nullptr) {
    return false;
  }
  String dir = parentDir(path);
  if (dir.length() > 1) {
    mkdirRecursive(dir.c_str());
  }
  FsFile f = sd.open(path, O_WRONLY | O_CREAT | O_APPEND);
  if (!f) {
    return false;
  }
  size_t n = strlen(data);
  size_t w = f.write(reinterpret_cast<const uint8_t*>(data), n);
  f.close();
  return w == n;
}

bool removeFile(const char* path) {
  if (!mounted || path == nullptr) {
    return false;
  }
  return sd.remove(path);
}

size_t fileSize(const char* path) {
  if (!mounted || path == nullptr || !sd.exists(path)) {
    return 0;
  }
  FsFile f = sd.open(path, O_RDONLY);
  if (!f) {
    return 0;
  }
  size_t n = f.fileSize();
  f.close();
  return n;
}

bool readLineAt(const char* path, size_t& offset, String& outLine) {
  outLine = "";
  if (!mounted || path == nullptr) {
    return false;
  }
  FsFile f = sd.open(path, O_RDONLY);
  if (!f) {
    return false;
  }
  if (!f.seekSet(offset)) {
    f.close();
    return false;
  }
  if (!f.available()) {
    f.close();
    return false;
  }
  while (f.available()) {
    char c = static_cast<char>(f.read());
    offset++;
    if (c == '\n') {
      break;
    }
    if (c != '\r') {
      outLine += c;
    }
  }
  f.close();
  return true;
}

bool ensureLayout() {
  bool ok = true;
  ok &= mkdirRecursive("/AOS");
  ok &= mkdirRecursive("/AOS/AGENT");
  ok &= mkdirRecursive("/AOS/MODULES");
  ok &= mkdirRecursive("/AOS/MODULES/profiles");
  ok &= mkdirRecursive("/AOS/INSTALL");
  ok &= mkdirRecursive("/AOS/LOGS");
  return ok;
}

}  // namespace SdStore
