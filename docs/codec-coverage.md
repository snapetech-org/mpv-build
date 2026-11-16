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
