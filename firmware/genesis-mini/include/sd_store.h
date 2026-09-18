#pragma once

#include <Arduino.h>

namespace SdStore {

bool begin();
bool isMounted();
void end();

bool exists(const char* path);
bool mkdirRecursive(const char* path);
bool readFile(const char* path, String& out);
bool writeFile(const char* path, const char* data);
bool appendFile(const char* path, const char* data);
bool removeFile(const char* path);
size_t fileSize(const char* path);

// Ensure standard AOS directories exist under /AOS
bool ensureLayout();

}  // namespace SdStore
