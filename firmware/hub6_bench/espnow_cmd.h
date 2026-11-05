// espnow_cmd.h: which ESP-NOW lines are commands for this sketch.
//
// The lines come from exp-cubic-earth's espnow_bridge (a XIAO on the host), which broadcasts every
// line it is given, or sends "!AA:BB:CC:DD:EE:FF <line>" to one MAC only. The cubic earth's modules
// hear the same broadcasts, and their commands ("#b", "#f1,2,3", ...) contain this sketch's letters,
// so a broadcast is taken only when it starts with "@dodeca "; a line sent to this XIAO alone is
// taken whole (with or without the prefix).
#pragma once
#include <stdint.h>
#include <string.h>

static const char ESPNOW_PREFIX[] = "@dodeca ";

// The command in data[0..n) (one packet, one line), copied into out with a terminating 0, or -1 if
// it is not for this sketch, empty, or does not fit in cap - 1 characters. toMe: sent to this
// XIAO's MAC, not broadcast.
inline int espnowCommand(const uint8_t *data, int n, bool toMe, char *out, int cap) {
  const char *s = reinterpret_cast<const char *>(data);
  while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) n--;
  const int p = (int)sizeof ESPNOW_PREFIX - 1;
  if (n >= p && memcmp(s, ESPNOW_PREFIX, p) == 0) {
    s += p;
    n -= p;
    while (n > 0 && *s == ' ') s++, n--;
  } else if (!toMe) {
    return -1;
  }
  if (n <= 0 || n >= cap) return -1;
  memcpy(out, s, n);
  out[n] = 0;
  return n;
}
