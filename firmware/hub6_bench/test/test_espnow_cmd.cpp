// Host test for espnow_cmd.h, from firmware/hub6_bench: g++ -std=c++17 -Wall -Wextra -I. test/test_espnow_cmd.cpp -o /tmp/t && /tmp/t
#include <cassert>
#include <cstdio>
#include <cstring>

#include "espnow_cmd.h"

static int cmd(const char *s, bool toMe, char *out) {
  return espnowCommand(reinterpret_cast<const uint8_t *>(s), (int)strlen(s), toMe, out, 32);
}

int main() {
  char out[32];
  // unicast to this XIAO (espnow_bridge "!MAC e"): the whole line, newline dropped
  assert(cmd("e\n", true, out) == 1 && strcmp(out, "e") == 0);
  assert(cmd("f 40\r\n", true, out) == 4 && strcmp(out, "f 40") == 0);
  // broadcast: only lines for "@dodeca "
  assert(cmd("@dodeca i\n", false, out) == 1 && strcmp(out, "i") == 0);
  assert(cmd("@dodeca   r 3\n", false, out) == 3 && strcmp(out, "r 3") == 0);
  // the cubic earth's broadcasts ("#b" would otherwise read as this sketch's b, "#f.." as f) are not ours
  assert(cmd("#b\n", false, out) == -1);
  assert(cmd("#f1,2,3\n", false, out) == -1);
  assert(cmd("e\n", false, out) == -1);
  assert(cmd("@dodecahedron e\n", false, out) == -1);
  assert(cmd("@dodeca\n", false, out) == -1);  // nothing to do
  // a prefixed line sent to this XIAO alone also works
  assert(cmd("@dodeca e\n", true, out) == 1 && strcmp(out, "e") == 0);
  // empty lines and lines too long for the buffer are dropped
  assert(cmd("\n", true, out) == -1);
  char longl[64];
  memset(longl, 'e', 40);
  longl[40] = 0;
  assert(cmd(longl, true, out) == -1);
  // no terminating newline is fine (one packet is one line)
  assert(cmd("b", true, out) == 1 && strcmp(out, "b") == 0);
  puts("espnow_cmd: ok");
  return 0;
}
