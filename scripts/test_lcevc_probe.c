#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "lcevc_probe.h"

int main(void)
{
    const uint8_t h264[] = {6, 4, 5, 0xb4, 0, 0x50, 0, 0x11, 0x80};
    const uint8_t hevc[] = {78, 1, 4, 5, 0xb4, 0, 0x50, 0, 0x11, 0x80};
    const uint8_t escaped[] = {6, 5, 3, 0, 0, 3, 1, 4, 5, 0xb4, 0, 0x50, 0, 0x11, 0x80};
    assert(mp_lcevc_nal(false, h264, sizeof(h264)));
    assert(mp_lcevc_nal(true, hevc, sizeof(hevc)));
    assert(mp_lcevc_nal(false, escaped, sizeof(escaped)));
    for (size_t size = 0; size < 8; size++)
        assert(!mp_lcevc_nal(false, h264, size));
    for (size_t size = 0; size < 9; size++)
        assert(!mp_lcevc_nal(true, hevc, size));
    uint8_t other[sizeof(h264)];
    memcpy(other, h264, sizeof(other));
    other[3] = 0xb5; // HDR10+/closed-caption country, not LCEVC
    assert(!mp_lcevc_nal(false, other, sizeof(other)));
    other[3] = 0xb4;
    other[1] = 5; // Unregistered user data with coincidental marker bytes
    assert(!mp_lcevc_nal(false, other, sizeof(other)));
    other[1] = 4;
    other[2] = 255; // Truncated payload-size extension
    assert(!mp_lcevc_nal(false, other, sizeof(other)));
    for (unsigned prefix = 1; prefix <= 4; prefix++) {
        uint8_t packet[32] = {0};
        packet[prefix - 1] = sizeof(h264);
        memcpy(packet + prefix, h264, sizeof(h264));
        assert(mp_lcevc_probe(false, packet, prefix + sizeof(h264), prefix));
        assert(!mp_lcevc_probe(false, packet, prefix + sizeof(h264) - 1, prefix));
    }
    uint8_t annex[32] = {0, 0, 0, 1};
    memcpy(annex + 4, hevc, sizeof(hevc));
    assert(mp_lcevc_probe(true, annex, 4 + sizeof(hevc), 4));
    memmove(annex + 3, annex + 4, sizeof(hevc));
    annex[2] = 1;
    assert(mp_lcevc_probe(true, annex, 3 + sizeof(hevc), 0));
    uint8_t extended[320] = {6, 5, 255, 45};
    memset(extended + 4, 0x7f, 300);
    memcpy(extended + 304, h264 + 1, sizeof(h264) - 1);
    assert(mp_lcevc_nal(false, extended, 304 + sizeof(h264) - 1));
    // Exercise every truncation and both framing paths under sanitizers.
    uint32_t seed = 1;
    uint8_t random[256];
    for (unsigned round = 0; round < 1000; round++) {
        for (size_t i = 0; i < sizeof(random); i++) {
            seed = seed * 1664525U + 1013904223U;
            random[i] = seed >> 24;
        }
        for (size_t size = 0; size <= sizeof(random); size++) {
            (void)mp_lcevc_probe(round & 1, random, size, round % 5);
            (void)mp_lcevc_nal(round & 1, random, size);
        }
    }
    puts("LCEVC AVC/HEVC framing, metadata identity and truncation checks passed");
    return 0;
}
