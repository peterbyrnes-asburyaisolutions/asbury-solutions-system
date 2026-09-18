#include <unity.h>

#include "sync_protocol.h"

#include <cstring>
#include <string>
#include <vector>

using SyncProtocol::MemoryLine;
using SyncProtocol::SyncMessage;

void test_device_id_validation() {
  TEST_ASSERT_TRUE(SyncProtocol::isValidDeviceId("genesis-mini-001"));
  TEST_ASSERT_TRUE(SyncProtocol::isValidDeviceId("user@example.com"));
  TEST_ASSERT_TRUE(SyncProtocol::isValidDeviceId("a+b_c.d"));
  TEST_ASSERT_FALSE(SyncProtocol::isValidDeviceId(""));
  TEST_ASSERT_FALSE(SyncProtocol::isValidDeviceId("."));
  TEST_ASSERT_FALSE(SyncProtocol::isValidDeviceId(".."));
  TEST_ASSERT_FALSE(SyncProtocol::isValidDeviceId("bad/id"));
  TEST_ASSERT_FALSE(SyncProtocol::isValidDeviceId("has space"));
}

void test_cursor_roundtrip() {
  uint64_t offset = 99;
  TEST_ASSERT_TRUE(SyncProtocol::parseCursor("12345\n", offset));
  TEST_ASSERT_EQUAL_UINT64(12345ULL, offset);
  TEST_ASSERT_TRUE(SyncProtocol::parseCursor("", offset));
  TEST_ASSERT_EQUAL_UINT64(0ULL, offset);
  TEST_ASSERT_TRUE(SyncProtocol::parseCursor("  7  \n", offset));
  TEST_ASSERT_EQUAL_UINT64(7ULL, offset);
  TEST_ASSERT_FALSE(SyncProtocol::parseCursor("nope", offset));
  TEST_ASSERT_EQUAL_STRING("42\n", SyncProtocol::formatCursor(42).c_str());
}

void test_daily_session_id() {
  // 2024-01-02 00:00:00 UTC
  const int64_t epoch = 1704153600LL;
  const std::string sid =
      SyncProtocol::dailySessionId("genesis-mini-001", epoch);
  TEST_ASSERT_EQUAL_STRING("genesis-mini-001-20240102", sid.c_str());
}

void test_parse_memory_line_and_skip_uptime() {
  const MemoryLine wall = SyncProtocol::parseMemoryLine(
      "{\"ts\":1700000001000,\"role\":\"user\",\"text\":\"hello\"}");
  TEST_ASSERT_TRUE(wall.ok);
  TEST_ASSERT_FALSE(wall.uptimeClock);
  TEST_ASSERT_EQUAL_STRING("user", wall.role.c_str());
  TEST_ASSERT_EQUAL_STRING("hello", wall.text.c_str());
  TEST_ASSERT_TRUE(SyncProtocol::shouldIncludeInBatch(wall));

  const MemoryLine up = SyncProtocol::parseMemoryLine(
      "{\"ts\":1234,\"clock\":\"uptime\",\"role\":\"user\",\"text\":\"boot\"}");
  TEST_ASSERT_TRUE(up.ok);
  TEST_ASSERT_TRUE(up.uptimeClock);
  TEST_ASSERT_FALSE(SyncProtocol::shouldIncludeInBatch(up));
}

void test_build_memorize_add_payload() {
  std::vector<SyncMessage> msgs;
  SyncMessage m;
  m.senderId = "dev1";
  m.role = "user";
  m.timestampMs = 1700000001000LL;
  m.content = "hi \"there\"";
  msgs.push_back(m);

  const std::string json =
      SyncProtocol::buildMemorizeAddJson("dev1-20231114", "dev1", msgs);
  TEST_ASSERT_NOT_NULL(strstr(json.c_str(), "\"session_id\":\"dev1-20231114\""));
  TEST_ASSERT_NOT_NULL(strstr(json.c_str(), "\"app_id\":\"genesis-mini\""));
  TEST_ASSERT_NOT_NULL(strstr(json.c_str(), "\"project_id\":\"dev1\""));
  TEST_ASSERT_NOT_NULL(strstr(json.c_str(), "\"sender_id\":\"dev1\""));
  TEST_ASSERT_NOT_NULL(strstr(json.c_str(), "\"timestamp\":1700000001000"));
  TEST_ASSERT_NOT_NULL(strstr(json.c_str(), "hi \\\"there\\\""));
}

void test_rag_context_cap() {
  const std::string resp =
      "{\"data\":{\"episodes\":["
      "{\"summary\":\"Alpha fact about the garden\"},"
      "{\"summary\":\"Beta fact about the kitchen\"},"
      "{\"summary\":\"Gamma fact about the workshop that is quite long and "
      "should eventually be truncated when the Relevant memory block exceeds "
      "the configured character budget for on-device LLM prompts\"}"
      "]}}";
  const std::string ctx = SyncProtocol::formatRagContext(resp);
  TEST_ASSERT_TRUE(ctx.find("Relevant memory:") == 0);
  TEST_ASSERT_TRUE(ctx.find("Alpha fact") != std::string::npos);
  TEST_ASSERT_TRUE(ctx.size() <= SyncProtocol::kRagContextCap);
}

void test_search_json() {
  const std::string body =
      SyncProtocol::buildSearchJson("dev1", "where is the wrench?", 3);
  TEST_ASSERT_NOT_NULL(strstr(body.c_str(), "\"user_id\":\"dev1\""));
  TEST_ASSERT_NOT_NULL(strstr(body.c_str(), "\"project_id\":\"dev1\""));
  TEST_ASSERT_NOT_NULL(strstr(body.c_str(), "\"top_k\":3"));
  TEST_ASSERT_NOT_NULL(strstr(body.c_str(), "where is the wrench?"));
}

void test_batch_cursor_skip_uptime_logic() {
  // Simulate reading three lines: uptime, wall, uptime — only one message,
  // but cursor should advance past all consumed bytes.
  const char* lines[] = {
      "{\"ts\":1,\"clock\":\"uptime\",\"role\":\"user\",\"text\":\"a\"}\n",
      "{\"ts\":1700000001000,\"role\":\"assistant\",\"text\":\"b\"}\n",
      "{\"ts\":2,\"clock\":\"uptime\",\"role\":\"user\",\"text\":\"c\"}\n",
  };
  uint64_t cursor = 0;
  std::vector<SyncMessage> msgs;
  for (const char* raw : lines) {
    const std::size_t n = strlen(raw);
    cursor += n;
    MemoryLine parsed = SyncProtocol::parseMemoryLine(raw);
    if (SyncProtocol::shouldIncludeInBatch(parsed)) {
      msgs.push_back(SyncProtocol::toSyncMessage(parsed, "dev1"));
    }
  }
  TEST_ASSERT_EQUAL(1, static_cast<int>(msgs.size()));
  TEST_ASSERT_EQUAL_STRING("assistant", msgs[0].role.c_str());
  TEST_ASSERT_EQUAL_UINT64(
      static_cast<uint64_t>(strlen(lines[0]) + strlen(lines[1]) + strlen(lines[2])),
      cursor);
}

int main(int argc, char** argv) {
  UNITY_BEGIN();
  RUN_TEST(test_device_id_validation);
  RUN_TEST(test_cursor_roundtrip);
  RUN_TEST(test_daily_session_id);
  RUN_TEST(test_parse_memory_line_and_skip_uptime);
  RUN_TEST(test_build_memorize_add_payload);
  RUN_TEST(test_rag_context_cap);
  RUN_TEST(test_search_json);
  RUN_TEST(test_batch_cursor_skip_uptime_logic);
  return UNITY_END();
}
