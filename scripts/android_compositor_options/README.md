# Android compositor JNI probe

Use a task-owned emulator and isolated native checkout. The probe exercises
initial option parsing, runtime read/write, native range rejection and player
shutdown. It creates no video window and does not qualify physical TV timing.
The additional source root is outside the production AAR source tree, so the
probe does not alter the release package's content key.

Set `PLEAZYNG_COMPOSITOR_QA_SOURCE` to this directory, then build the library's
`assembleDebugAndroidTest` task with this `init.gradle` via `-I`, four verified
native tarballs via `-Pmpv.tarballs`, and the emulator's ABI through
`-Pandroid.injected.build.abi`. Bound desktop Gradle work to two CPUs/workers.
Use the AGP redirect file and referenced output metadata to locate the new APK.
Install it with `adb -s SERIAL install -t -r APK`, then run:

```sh
adb -s SERIAL shell am instrument -w -r \
  -e class com.edde746.mpv.CompositorOptionsDeviceTest \
  com.edde746.mpv.test/androidx.test.runner.AndroidJUnitRunner
```

For actual surface rendering, also run
`MpvPlayerDeviceTest#playsThroughSurfaceHandoffsAndStopsDeliveringOnClose` with
its `mediaUrl` argument. The synthetic fixture in `scripts/avf_shader_playback`
can be pushed to the owned emulator's `/data/local/tmp`, then copied into the
debug test application's private `files` directory with `run-as`. Verify its
SHA-256 before playback.
