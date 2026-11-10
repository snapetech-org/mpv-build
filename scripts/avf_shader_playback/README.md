# Headless AVFoundation playback fixture

Run `bash scripts/qa_avf_shader_playback.sh <Libmpv.xcframework.zip> <task-output-directory>`
on a real Metal-capable Mac. Set `AVF_QA_BUILD_ROOT` to reuse a task-owned local
Swift build cache. The probe retains its inputs and playback log, creates no
window, and exits with failure after 40 seconds if initialization or shutdown
hangs. It verifies real hardware-decoded GLSL frames at both picture-sized and
ambient-style stretched output sizes. It does not qualify Dolby Vision, TV
scanout timing, or heavy-preset performance.

This caught the ordered-PCM teardown deadlock during embedded Cocoa client
initialization. Keep mpv calls on a worker while the main run loop services
AVFoundation layer callbacks.

The video is a synthetic, silent test pattern generated for this repository:

```sh
ffmpeg -f lavfi -i testsrc2=size=320x180:rate=24 -t 2 -c:v libx264 -pix_fmt yuv420p fixture.mp4
```

It contains no third-party media. `identity.glsl` is a minimal pass-through
shader used to establish that the real shader stage executed.

## Upstream sources

[@edde746](https://github.com/edde746) contributed the
[AVFoundation shader stage](https://github.com/edde746/mpv-build/commit/2b23527)
and [stretch geometry](https://github.com/edde746/mpv-build/commit/9929c5e)
to the upstream project. Pleazyng independently integrated and qualified them
with this probe. See the [fork attribution ledger](https://github.com/snapetech-org/pleazyng/blob/main/UPSTREAM_ATTRIBUTION.md).
