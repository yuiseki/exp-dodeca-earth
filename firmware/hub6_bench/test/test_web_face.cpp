// Host test for web_face.h, from firmware/hub6_bench: g++ -std=c++17 -Wall -Wextra -I. test/test_web_face.cpp -o /tmp/t && /tmp/t
#include <cassert>
#include <cstdio>
#include <cstring>

#include "web_face.h"

int main() {
  char url[128];
  // <base>/<name>-<face>.jpg, with a query that changes every call so a cache in front of the server
  // does not hand back yesterday's image under the same name
  assert(faceUrl(url, sizeof url, "https://example.org/dodeca-earth", "upper", "P1", 1234));
  assert(strcmp(url, "https://example.org/dodeca-earth/upper-P1.jpg?t=1234") == 0);
  assert(faceUrl(url, sizeof url, "https://example.org/d", "lower", "BASE", 0));
  assert(strcmp(url, "https://example.org/d/lower-BASE.jpg?t=0") == 0);
  // a name is letters, digits, '-' and '_' only (it comes over ESP-NOW)
  assert(!faceUrl(url, sizeof url, "https://example.org/d", "../x", "P1", 0));
  assert(!faceUrl(url, sizeof url, "https://example.org/d", "", "P1", 0));
  assert(!faceUrl(url, sizeof url, "https://example.org/d", "a b", "P1", 0));
  // too long for the buffer: false, and no overrun
  char small[20];
  memset(small, 'x', sizeof small);
  assert(!faceUrl(small, sizeof small, "https://example.org/dodeca-earth", "upper", "P1", 1));
  puts("web_face: ok");
  return 0;
}
