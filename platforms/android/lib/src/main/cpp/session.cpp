#include "session.h"

#include <map>
#include <mutex>

namespace {

std::mutex& registry_lock() {
  static std::mutex lock;
  return lock;
}

std::map<uint64_t, std::shared_ptr<Session>>& registry() {
  static std::map<uint64_t, std::shared_ptr<Session>> sessions;
  return sessions;
}

uint64_t next_id = 0;

}  // namespace

Session::Session(uint64_t id, mpv_handle* handle) : id(id), handle(handle) {}

Session::~Session() {
  pthread_rwlock_destroy(&admission);
  pthread_mutex_destroy(&surface_lock);
}

std::shared_ptr<Session> session_register(mpv_handle* handle) {
  std::lock_guard<std::mutex> lock(registry_lock());
  std::shared_ptr<Session> session = std::make_shared<Session>(++next_id, handle);
  registry()[session->id] = session;
  return session;
}

std::shared_ptr<Session> session_find(uint64_t id) {
  std::lock_guard<std::mutex> lock(registry_lock());
  auto entry = registry().find(id);
  return entry == registry().end() ? nullptr : entry->second;
}

std::shared_ptr<Session> session_retire(uint64_t id) {
  std::lock_guard<std::mutex> lock(registry_lock());
  auto entry = registry().find(id);
  if (entry == registry().end()) return nullptr;
  std::shared_ptr<Session> session = entry->second;
  registry().erase(entry);
  return session;
}

SessionGuard::SessionGuard(jlong id) : session(session_find((uint64_t)id)) {
  if (!session) return;
  pthread_rwlock_rdlock(&session->admission);
  if (!session->retired) mpv = session->handle;
}

SessionGuard::~SessionGuard() {
  if (session) pthread_rwlock_unlock(&session->admission);
}

// Optional Plezy visualization bridge v1. A registry identity, never a raw mpv
// pointer, crosses into the application. SessionGuard admits each read through
// its final mpv use, so session retirement cannot free a live PCM consumer.
#include <dlfcn.h>
#include <mpv/plezy_audio_tap.h>
#include <cmath>
namespace {
struct PlezyTapApi {
  int (*version)() = reinterpret_cast<int(*)()>(dlsym(RTLD_DEFAULT, "mpv_plezy_audio_tap_version"));
  int (*enable)(mpv_handle*, int) = reinterpret_cast<int(*)(mpv_handle*, int)>(dlsym(RTLD_DEFAULT, "mpv_plezy_audio_tap_enable"));
  int (*read)(mpv_handle*, double, mpv_plezy_audio_block*, size_t) = reinterpret_cast<int(*)(mpv_handle*, double, mpv_plezy_audio_block*, size_t)>(dlsym(RTLD_DEFAULT, "mpv_plezy_audio_tap_read"));
  int (*read_next)(mpv_handle*, mpv_plezy_audio_block*, size_t) = reinterpret_cast<int(*)(mpv_handle*, mpv_plezy_audio_block*, size_t)>(dlsym(RTLD_DEFAULT, "mpv_plezy_audio_tap_read_next"));
  bool available() const { return version && enable && read && version() == 1; }
  bool subtitle_available() const { return version && enable && read_next && version() == 1; }
};
PlezyTapApi& plezy_tap() { static PlezyTapApi api; return api; }
}
extern "C" __attribute__((visibility("default"))) int plezy_android_visualization_version() {
  return plezy_tap().available() ? 1 : 0;
}
extern "C" __attribute__((visibility("default"))) int plezy_android_visualization_enable(uint64_t id, int enabled) {
  try { SessionGuard guard(static_cast<jlong>(id));
    return guard.mpv && plezy_tap().available() ? plezy_tap().enable(guard.mpv, enabled) : MPV_ERROR_UNINITIALIZED;
  } catch (...) { return MPV_ERROR_GENERIC; }
}
extern "C" __attribute__((visibility("default"))) int plezy_android_visualization_read(uint64_t id, void* output, size_t size) {
  try { SessionGuard guard(static_cast<jlong>(id));
    if (!guard.mpv || !plezy_tap().available()) return MPV_ERROR_UNINITIALIZED;
    const auto pts = guard.session->visualization_pts.load();
    return std::isfinite(pts) ? plezy_tap().read(guard.mpv, pts, static_cast<mpv_plezy_audio_block*>(output), size) : 0;
  } catch (...) { return MPV_ERROR_GENERIC; }
}
extern "C" __attribute__((visibility("default"))) int plezy_android_subtitle_capture_read_next(uint64_t id, void* output, size_t size) {
  try { SessionGuard guard(static_cast<jlong>(id));
    if (!guard.mpv || !plezy_tap().subtitle_available()) return MPV_ERROR_UNINITIALIZED;
    return plezy_tap().read_next(guard.mpv, static_cast<mpv_plezy_audio_block*>(output), size);
  } catch (...) { return MPV_ERROR_GENERIC; }
}
