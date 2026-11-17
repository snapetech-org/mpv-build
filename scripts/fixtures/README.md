# Blu-ray title fixture

`bluray-title.tar.xz` contains an unencrypted, synthetic eight-second BDMV
title with chapter marks at zero, two, four and six seconds. The source is
an FFmpeg-generated color field with two rectangles.

Generate the AVC stream with FFmpeg 7.1 and author the tree with
[tsMuxeR 2.7.0](https://github.com/justdan96/tsMuxer/tree/f06ac394c55ccee1cb76ae54f4636532a2d10253).
The authoring tool is only needed to regenerate the fixture.

```sh
mkdir -p small
ffmpeg -f lavfi -i "color=c=steelblue:s=1280x720:r=50:d=8,drawbox=x=40:y=80:w=200:h=300:color=yellow:t=fill,drawbox=x=300:y=80:w=200:h=300:color=firebrick:t=fill:enable='gte(t,4)'" \
  -c:v libx264 -crf 36 -preset ultrafast -threads 1 -g 25 -sc_threshold 0 \
  -pix_fmt yuv420p -f h264 small.h264
cat > small.meta <<'EOF'
MUXOPT --blu-ray --cbr --bitrate=2000 --custom-chapters=00:00:00.000;00:00:02.000;00:00:04.000;00:00:06.000
V_MPEG4/ISO/AVC, "small.h264", fps=50
EOF
tsMuxeR small.meta small
tar --sort=name --mtime='UTC 2020-01-01' --owner=0 --group=0 --numeric-owner \
  -cJf bluray-title.tar.xz -C small BDMV CERTIFICATE
```

The consistent mux rate keeps enough packet data for a real random-access seek
while the archive stays small. The pinned archive hash is in
`scripts/codec_disc_smoke.py`.
