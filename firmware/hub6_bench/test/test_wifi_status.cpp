// Host test for wifi_status.h, from firmware/hub6_bench: g++ -std=c++17 -Wall -Wextra -I. test/test_wifi_status.cpp -o /tmp/t && /tmp/t
#include <cassert>
#include <cstdio>
#include <cstring>

#include "wifi_status.h"

int main() {
  char out[120];
  // joined: the AP, the channel the radio is on, the signal, the address, and how long since boot
  wifiStatusLine(out, sizeof out, true, "pi5-w-1", 6, 1, -41, "10.42.0.57", 754);
  assert(strcmp(out, "wifi: pi5-w-1, channel 6, rssi -41, ip 10.42.0.57, up 754 s") == 0);
  // not joined: the channel the radio is on, next to the one setupEspnow asked for, so a fallback that did not
  // take effect shows
  wifiStatusLine(out, sizeof out, false, "", 6, 1, 0, "0.0.0.0", 12);
  assert(strcmp(out, "wifi: no AP, channel 6 (asked for 1), up 12 s") == 0);
  wifiStatusLine(out, sizeof out, false, "", 1, 1, 0, "0.0.0.0", 12);
  assert(strcmp(out, "wifi: no AP, channel 1 (asked for 1), up 12 s") == 0);
  // a small buffer is cut, not overrun
  char small[10];
  memset(small, 'x', sizeof small);
  wifiStatusLine(small, sizeof small, true, "pi5-w-1", 6, 1, -41, "10.42.0.57", 754);
  assert(strlen(small) == sizeof small - 1);
  puts("wifi_status: ok");
  return 0;
}
