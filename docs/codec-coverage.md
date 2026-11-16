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

The Linux build now links pinned static XEVD (EVC Main/Baseline), davs2 (AVS2),
and uavs3d (AVS3, including its 10-bit build). Their source pins participate in
the package content key. The final loaded-library gate requires `evc`, `avs2`
and `avs3`, so a successful dependency build alone cannot pass publication.
The pinned davs2 release only accepts an 8-bit build; 10-bit AVS2 is **not**
covered by this recipe. These additions do not imply inclusion on other targets.

Local x86_64 validation on 2026-11-16 built all three static libraries, linked
their wrappers into the pinned FFmpeg revision
`46f23be8b1976ed4c8ec85584daabcf0e57a7b9e`, and decoded ten frames of the
official FATE `evc/akiyo_cif.evc` sample with `-xerror` successfully. AVS2/AVS3
media execution, ARM64 builds and packaged libmpv execution remain separate
qualification requirements.

AV2 is a named source identity, not an installed FFmpeg decoder. The reviewed
dav2d source currently requires a separate FFmpeg integration and uses evolving
AV2 syntax. LCEVC enhancement reconstruction likewise needs an external library
and a correctly connected enhancement path; decoding its base layer does not
qualify as LCEVC reconstruction.

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
