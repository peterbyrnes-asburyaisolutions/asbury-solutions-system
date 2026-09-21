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

// Read one line starting at *offset (byte position). On success, *offset is
// advanced past the newline (or to EOF). outLine excludes the newline.
// Returns false at EOF or on error.
bool readLineAt(const char* path, size_t& offset, String& outLine);

// Ensure standard AOS directories exist under /AOS
bool ensureLayout();

}  // namespace SdStore
