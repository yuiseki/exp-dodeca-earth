// wifi_status.h: the reply to the "w" command, one line about the radio.
//
// ESP-NOW only reaches this XIAO when its radio is on the bridge's channel. Joined to an AP, that is the
// AP's channel; not joined, it is whatever the radio was left on, which setupEspnow tries to set to
// ESPNOW_CHANNEL. The line shows both, so "it works" can be told apart from "it works by chance".
#pragma once
#include <stdint.h>
#include <stdio.h>

inline void wifiStatusLine(char *out, int cap, bool joined, const char *ssid, int channel, int askedChannel, int rssi,
                           const char *ip, uint32_t upS) {
  if (joined)
    snprintf(out, cap, "wifi: %s, channel %d, rssi %d, ip %s, up %lu s", ssid, channel, rssi, ip, (unsigned long)upS);
  else
    snprintf(out, cap, "wifi: no AP, channel %d (asked for %d), up %lu s", channel, askedChannel, (unsigned long)upS);
}
