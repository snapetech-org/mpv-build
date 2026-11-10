# Compositor integration qualification — 2026-11-09

Normal packages contain Amlogic letterbox control, per-frame delayed Android
subtitle presentation, and the AVFoundation GLSL stage with stretched output.
Existing FEL/HDR/neural components and runtime Settings choices are retained.

| Package | Key | Qualification |
| --- | --- | --- |
| Android engine | `6168c50b5c17` | All four ABIs compiled; compositor options, ordered PCM and neural components inspected |
| Android AAR | `82ace919fd97` | JVM tests passed; packaged ABI/component checks passed |
| Apple Libmpv | `93fdd133cea1` | All six platform groups and all eleven architecture slices built and inspected; iOS/tvOS consumers linked |

- [Android producer run](https://github.com/snapetech-org/mpv-build/actions/runs/42728730494)
- [Apple producer run](https://github.com/snapetech-org/mpv-build/actions/runs/42731121521)
- [Apple assembly and consumer links](https://github.com/snapetech-org/mpv-build/actions/runs/42735647569)

Real headless playback on macOS 27.0 / Apple M4 passed initialization,
VideoToolbox decoding, GLSL rendering at 640×360, ambient-style stretching to
640×480, and shutdown. Use `scripts/qa_avf_shader_playback.sh` to reproduce it.
The probe found a cold-start deadlock: a temporary Cocoa client was destroyed
while initialization held the core lock, and unconditionally disabling an
unowned ordered-PCM tap tried to acquire that lock again. Apple patch 0170
skips teardown for handles without a tap; actual tap owners retain retirement.
Do not promote the earlier `e9db12fb98de` Apple package lacking this fix.

A task-owned API-36 x86_64 Android TV emulator passed two real instrumentation
checks: compositor option initialization/read/write/range validation through
JNI, and video playback across Surface replacement and shutdown. The engine
binaries matched the production Android content key. The additional JNI probe
is in `scripts/android_compositor_options`; the Surface test is maintained in
the native library's existing device suite.

Portable scheduler, unchanged-content and rebind tests passed against both
standard and bundled-FEL Android patch stacks. Apple shader target sizing,
subtitle layer geometry and Dolby Vision profile selection checks passed.
`verify_avf_shaders.py` requires the real shader object's Vulkan/Metal imports
in every architecture; an archive exporting only fallback functions is rejected.

These results do not establish physical Amlogic/MediaTek display black levels,
subtitle scanout timing, Dolby Vision shader compatibility or heavy-preset
performance. The stage's documented runtime exclusions remain explicit.
Native capability receipts retain their own qualification scope.

## Upstream sources

[@edde746](https://github.com/edde746) contributed the
[shader stage](https://github.com/edde746/mpv-build/commit/2b23527),
[stretch geometry](https://github.com/edde746/mpv-build/commit/9929c5e),
[letterbox control](https://github.com/edde746/mpv-build/commit/bc87af7),
[early subtitle queue](https://github.com/edde746/mpv-build/commit/98452a9) and
[unchanged-frame repetition](https://github.com/edde746/mpv-build/commit/8958474)
to upstream mpv-build. Pleazyng independently integrated and verified them;
this does not imply direct contribution to or endorsement of this fork.
See [the fork attribution ledger](https://github.com/snapetech-org/pleazyng/blob/main/UPSTREAM_ATTRIBUTION.md).
