// web_face.h: where the j command fetches a face from: <base>/<name>-<face>.jpg?t=<t>.
//
// make_earth_faces.py --jpeg-dir writes the six JPEGs under these names. The query changes on every
// fetch, so a cache in front of the web server (Cloudflare) does not answer with an older image that
// had the same name. The name arrives over ESP-NOW, so only letters, digits, '-' and '_' are taken.
#pragma once
#include <stdio.h>
#include <string.h>

inline bool faceNameOk(const char *name) {
  if (!name || !*name) return false;
  for (const char *c = name; *c; c++) {
    bool ok = (*c >= 'a' && *c <= 'z') || (*c >= 'A' && *c <= 'Z') || (*c >= '0' && *c <= '9') || *c == '-' || *c == '_';
    if (!ok) return false;
  }
  return true;
}

inline bool faceUrl(char *out, int cap, const char *base, const char *name, const char *face, unsigned long t) {
  if (!faceNameOk(name)) return false;
  int n = snprintf(out, cap, "%s/%s-%s.jpg?t=%lu", base, name, face, t);
  return n > 0 && n < cap;
}
