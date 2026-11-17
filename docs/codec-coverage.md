# Decoder coverage

Codec availability is recorded from the **loaded binary**, not inferred from a
version number, FFmpeg's upstream feature list, or a source configuration flag.

`scripts/codec_inventory.py /absolute/path/to/libmpv.so --output inventory.json`
creates a hash-bound inventory of decoders, implementations, demuxers and
protocols. It opens no media, configuration, scripts or output devices. Run it
on a native host matching the library's architecture. `--require codec` fails
when a decoder is absent; requiring AV1 also requires a software implementation.
The existing Linux publication container runs this against both native
architectures and uploads the result with the build artifacts. Android and Apple
app runtime observations provide the same decoder/demuxer facts; a cross-compiled
library is not represented as having executed on its build host.

Android and Linux explicitly keep the complete built-in decoder, parser,
demuxer and bitstream-filter inventories enabled. Optional external libraries
still need their own build dependencies and implementation verification. An
inventory does not prove real-time performance, profile completeness, HDR output,
audio passthrough, 3D presentation or support for a particular container/codec
combination. `executionQualified` remains false until media/device tests supply
that separate evidence.

Validation: `python3 scripts/test_codec_inventory.py` checks native-node decoding
and failure conditions; `bash platforms/linux/test.sh` exercises the source
acquisition and build arguments. The library enumeration itself is a release
build gate and cannot be replaced by those unit checks.

## External video decoders

Linux links pinned static XEVD (EVC Main/Baseline), davs2 (8-bit AVS2), and
uavs3d (AVS3, including its 10-bit build). Android builds pinned XEVD, davs2
(8-bit AVS2), and 10-bit uavs3d for all four packaged ABIs and enables their
FFmpeg wrappers. Apple builds XEVD and 8-bit davs2 for each platform slice,
alongside its pinned AVS3 library, and merges both decoder archives into
`libavcodec.a`. Windows adds XEVD to the pinned winbuild graph alongside its
existing AVS2/AVS3 packages.
The Android AVS3 ARMv7 build deliberately uses upstream's portable C kernels:
its ARMv7 assembly recipe forces a hard-float calling convention that does not
match the Android `armeabi-v7a` ABI. Source pins participate in each platform's
package content key. Linux's loaded-library release gate requires
`h264`, `hevc`, software `av1`, `vp9`, `mpeg2video`, `vc1`,
`mpeg4`, `vvc`, `evc`, `avs2` and `avs3`; it also runs the generated
playback corpus and LCEVC reconstruction smoke on each native architecture.
Android, Apple, and Windows inventories and device execution remain separate
qualification steps. The pinned davs2 release only accepts an 8-bit build;
10-bit AVS2 is **not** covered.

Local x86_64 validation on 2026-11-16 linked all three external decoders
into pinned FFmpeg and decoded the official FATE EVC sample. AVS2 8-bit and
AVS3 8/10-bit output matches upstream YUV hashes. The full Linux package also
passed the corpus and LCEVC reconstruction gates described below.

The pinned Android NDK 29.0.14206865 is available locally: all four ABI SDK
clients and final shared FFmpeg libraries link successfully. Hosted run
43983813338 passed both Linux architectures, all four Android ABIs, the Android
AAR, and Linux/Android publication. Windows x86_64 built, but Windows publication failed because the required
ARM64 binary and symbols were absent after its build failed. Windows ARM64
failed in the LCEVC source build with x86 MMX intrinsic errors. That run
started before the Windows cache-key fix at `4235371`, so it does not qualify
the current Windows ARM64 source state.

Current `main` invalidates cached Windows source and build state when resolved
patches change. Its cache-invalidation regression tests pass locally. A fresh
same-commit Windows ARM64 build and successful package publication are still
required before that target is qualified or the app pin advances. Build success
also does not establish physical-device playback qualification. Earlier notes
saying the Android NDK was absent are superseded.

AV2 is not an installed FFmpeg decoder: this pin has no AV2 codec ID,
decoder wrapper or demuxer integration, and a dav2d SDK build alone cannot add
playback to mpv. VideoLAN's May 2026 status describes dav2d as an early,
functional decoder with 8/10-bit decoding, while conformance, optimization and
platform support remain active work. Keep AV2 out of measured decoder
inventories until the decoder is integrated with FFmpeg, validated against
AV2 v1.0.0 streams, and qualified on each target. The client should use a
server conversion only when the server offers a compatible route, and otherwise
report the unsupported source accurately.
Sources: [AV2 v1.0 specification](https://av2.aomedia.org/),
[VideoLAN dav2d status](https://jbkempf.com/blog/2026/dav2d/). LCEVC now has a pinned 4.3.1 static SDK source recipe on Linux, Android,
Windows and all Apple slices. Android packages it into its FFmpeg shared
libraries and carries the original notices in both native tarballs and AAR
assets. Windows links the static SDK into FFmpeg. Apple folds all eight SDK
archives into Libavcodec and retains notices in the framework resources.
These source integrations still require successful platform publication and
application pin updates before users receive them. Its installed
pkg-config descriptor is normalized so C++ runtime dependencies follow SDK
archives, including under `--as-needed`; a C client linked and initialized the
SDK successfully on x86_64. The recipe retains upstream COPYRIGHT and licensing
notices in the package prefix. This is SDK/API evidence, not yet a packaged
FFmpeg enhancement reconstruction result. Decoding only the base layer never
qualifies as LCEVC reconstruction.

The upstream SDK uses BSD-3-Clause-Clear and additional licensing information,
which remain its own terms and explicitly exclude a patent license. Bundling
the static implementation requires no SDK installation by end users. Preserve
both upstream `COPYING` and `LICENSE.md` in distributions; do not describe the
application license as replacing those terms. Sources: [LCEVCdec 4.3.1](https://github.com/v-novaltd/LCEVCdec/tree/e295d8438ba554bc541fb269baa9cbd567b626a8),
[licensing information](https://github.com/v-novaltd/LCEVCdec/blob/e295d8438ba554bc541fb269baa9cbd567b626a8/LICENSE.md).

## Generated-media release check

`scripts/codec_playback_smoke.py /absolute/path/to/libmpv.so --output report.json`
generates 28 short video/audio fixtures using the host FFmpeg, then decodes and
seeks each through the supplied libmpv in its own bounded worker process. It
forces software decoding. The video cases include AVC/HEVC/AV1/VP8/VP9, 10-bit
examples, MPEG-2/4, WMV2, ProRes, FFV1, HuffYUV, JPEG, Theora, FLV, QuickTime RLE
and Cinepak. Audio includes AAC, MP3, Opus, Vorbis, FLAC, ALAC, AC-3/E-AC-3,
24-bit PCM and WavPack. Audio output must contain the expected nonempty PCM
duration across initial playback and seeking; packet timestamp heuristics alone
are insufficient. Video must produce the expected output dimensions and finish
both playback passes. Reports bind the loaded binary and generated fixture
hashes to the results and explicitly exclude physical-output/performance claims.

Linux publication executes this after inventory and before packaging, on each
native architecture. The host FFmpeg creates media only; the decoder under test
is always the newly built library. A missing host encoder fails fixture creation
instead of silently skipping that family. Passing this corpus does not establish
every profile, bit depth, chroma mode, corrupt-input case, subtitle format or
audio/video combination in those families.

Harness validation on 2026-11-16: all 28 cases passed against Debian's x86_64
libmpv 0.40.0 (`0.40.0-3+deb13u1`). This validates the harness against a reference
engine; it is **not** a passing result for a new Pleazyng package. The newly
built library must pass this gate independently before its release.

## LCEVC reconstruction evidence

On 2026-11-16 the pinned FFmpeg and SDK built together on Linux x86_64.
Ten frames of the [official FATE H.264/LCEVC sample](https://fate-suite.ffmpeg.org/lcevc/L_H264_640x360p_8bit8bit_2D_dd.ts)
reconstructed from a 320×180 base layer to 640×360. All ten enhanced frame
hashes differed from the SDK's forced scale-only output at the same dimensions;
forced base passthrough remained 320×180. This demonstrates enhancement use,
not merely successful API initialization or base decoding. It is not packaged
libmpv, cross-platform, pixel-conformance or physical-device qualification.

Linux publication now additionally executes `scripts/lcevc_playback_smoke.py`
against the exact library being packaged, on both architectures. The hash-bound
fixture must decode and seek at 640×360 normally and 320×180 with forced base
passthrough. Reports explicitly distinguish this dimension check from pixel
conformance. A missing SDK or ignored enhancement fails publication.

### Hardware bypass and Android final-link fixes

A headless VA-API test on 2026-11-16 reproduced a silent 320×180 base-only
result with the SDK-linked FFmpeg. The SDK's CPU API cannot consume hardware
surfaces. The common mpv patch now detects a hardware frame retaining LCEVC
side data, retires that hardware route and replays the probing packets through
software. The same headless test then decoded and sought at 640×360. An ordinary
H.264 control remained on `vaapi-copy`; unrelated streams keep hardware decoding.
This is local Linux/VA-API evidence, not Android/VideoToolbox/D3D device qualification.

The exact pinned NDK 29.0.14206865 is available under the local Android SDK.
LCEVC SDK static builds and final C-client links passed for arm64-v8a,
armeabi-v7a, x86 and x86_64 at API 25, with `--as-needed` and 16 KiB page
alignment. These final links exposed and fixed the upstream static pkg-config
file's missing `-landroid` dependency for ANativeWindow symbols. Android uses
the packaged `libc++_shared.so`, rather than an unbundled C++ runtime. The
cross-compiled clients have not been executed on Android devices.

### AVS reference reconstruction and Android ABI coverage

The pinned native Linux decoders were built locally and linked into the pinned
FFmpeg on 2026-11-16. Full decoded YUV matched the upstream reference MD5 for
AVS2 8-bit BQSquare (`cf9babd3440b696c998179071a608b85`), AVS3 8-bit City
(`df6fff020f1e3e906237ee278c7db069`) and AVS3 10-bit MarketPlace
(`ea46707dd7200b23c51878c03e48ff0f`). These are individual reference-vector
results, not blanket profile, packaged-library or device qualification.
Sources: [AVS2 reference streams](https://github.com/pkuvcl/avs2stream/tree/96065ae3d3f940ebad5a0b84251b3cf27ecf201c),
[AVS3 reference streams](https://github.com/uavs3/avs3stream/tree/e9fcc4eac77061213c8fb07c87a8a1106fb66fe8).

All four Android ABIs now cross-build XEVD, davs2, 10-bit uavs3d and LCEVCdec
with the pinned NDK. XEVD's ARMv7 build uses its existing portable C path:
its NEON sources contain AArch64-only intrinsics and cannot compile for 32-bit
Android. ARM64 retains NEON. Android FFmpeg requests static pkg-config
information even though its own output is shared, so the static decoder
archives' private link dependencies are included.

Android final-link validation also passed for all four ABIs using shared
FFmpeg libraries with EVC, AVS2, AVS3 and LCEVC enabled together. The x86
probe caught another upstream CMake mismatch: NDK reports `i686`, but uavs3d
only recognized `i386`/`x86`, leaving its selected SIMD functions undefined at
link. The Android patch now recognizes i686 and includes those sources.
The resulting libraries depend on the packaged FFmpeg/libc++ libraries and
Android system libraries; no separately installed decoder SDK is required.
These minimal cross-builds do not replace the complete published libmpv/AAR
build or device execution qualification.

## SDK bundling decisions

| Dependency | Delivery decision |
| --- | --- |
| XEVD, davs2, uavs3d | Pinned static decoder code enters the normal native packages; root notices remain in native packages and the app. davs2 covers 8-bit AVS2. |
| LCEVCdec | Pinned static CPU implementation, matching C++ runtime and complete upstream notice tree. Android needs libandroid; Apple merges the SDK archives into Libavcodec. Users do not install an SDK. Hardware base-only output must fall back to reconstruction rather than masquerade as enhanced playback. |
| dav2d / AV2 | A public decoder exists, but this FFmpeg pin has no AV2 integration. Requires a codec/container implementation and reference-stream tests before availability can be advertised. [VideoLAN announcement](https://jbkempf.com/blog/2026/dav2d/), [released AV2 specification](https://av2.aomedia.org/v1.0.0/20260528_38f28e7_AV2_Spec_v1.0.0.pdf). |
| Fraunhofer MPEG-H decoder | A public C/C++ SDK and FFmpeg wrapper exist; source access does not require a proprietary account. This FFmpeg pin classifies libmpeghdec as nonfree. Its license retains source/notice requirements and excludes patent rights. This is not an enabled dependency in normal redistributable builds. [SDK source](https://github.com/Fraunhofer-IIS/mpeghdec), [SDK license](https://github.com/Fraunhofer-IIS/mpeghdec/blob/4448b69738da2fa5f2f2f2b0ce29eea32509e046/LICENSE.txt), [pinned FFmpeg configuration](https://github.com/FFmpeg/FFmpeg/blob/46f23be8b1976ed4c8ec85584daabcf0e57a7b9e/configure). |

FFmpeg states that enabling incompatible dependencies with `--enable-nonfree`
makes its resulting binary unredistributable; do not silently use that switch
to turn a missing decoder into a release checkbox. A separately authorized
component or a server conversion route needs its own delivery and execution
evidence. [FFmpeg licensing](https://www.ffmpeg.org/doxygen/4.3/md_LICENSE.html).

For every route, advertise the loaded decoder inventory and actual enhancement
use. Native webOS, Tizen and ExoPlayer do not gain optional SDKs from an mpv
package. Unsupported sources must use an available conversion route or report
the actual unsupported codec; a recognized extension is not a working feature.

### Detect enhancement before full hardware decoders

The packet path now checks LCEVC side data and AVC/HEVC registered-user-data
SEI before submitting packets to hardware, including full decoders such as
MediaCodec that need not return the SEI on their output frames. A bounded,
non-mutating probe supports Annex B and one-to-four-byte length prefixes,
skips unrelated/HDR metadata, handles emulation prevention and rejects truncated
payloads. It runs only when hardware is active and the loaded FFmpeg build
includes the LCEVC SDK. The pending packet is retried through the existing
software fallback rather than discarded. Frame-side detection remains a backup.

Address/undefined sanitizer checks cover both codecs, framing variants,
unrelated metadata and truncation/random inputs. A headless VA-API run verified
that enhanced video switches to software before hardware submission and decodes
and seeks at 640×360, while the ordinary AVC control remains on hardware.
This closes the signalling-loss path; it is not a claim of physical Android,
Apple or Windows device playback qualification.
