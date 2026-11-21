// swift-tools-version:5.8

import PackageDescription

let package = Package(
    name: "MPVKit",
    platforms: [.macOS(.v12), .iOS(.v15), .tvOS(.v15)],
    products: [
        .library(
            name: "MPVKit",
            targets: ["_MPVKit"]
        ),
    ],
    targets: [
        .target(
            name: "_MPVKit",
            dependencies: [
                "Libmpv", "_FFmpeg", "Libuchardet", "Libbluray",
                .target(name: "Libluajit", condition: .when(platforms: [.macOS])),
            ],
            path: "Sources/_MPVKit",
            linkerSettings: [
                .linkedFramework("Accelerate"),
                .linkedFramework("AVFoundation"),
                .linkedFramework("CoreImage"),
                .linkedFramework("CoreMedia"),
                .linkedFramework("CoreVideo"),
                .linkedFramework("Metal"),
                .linkedFramework("QuartzCore"),
                .linkedFramework("AppKit", .when(platforms: [.macOS])),
                .linkedFramework("UIKit", .when(platforms: [.iOS, .tvOS])),
                .linkedFramework("CoreAudio"),
            ]
        ),
        .target(
            name: "_FFmpeg",
            dependencies: [
                "Libavcodec", "Libavdevice", "Libavfilter", "Libavformat", "Libavutil", "Libswresample", "Libswscale",
                "Libssl", "Libcrypto", "Libass", "Libfreetype", "Libfribidi", "Libharfbuzz",
                "MoltenVK", "Libshaderc_combined", "lcms2", "Libplacebo", "Libdovi", "Libunibreak",
                "Libdav1d", "Libuavs3d"
            ],
            path: "Sources/_FFmpeg",
            linkerSettings: [
                .linkedFramework("AudioToolbox"),
                .linkedFramework("CoreVideo"),
                .linkedFramework("CoreFoundation"),
                .linkedFramework("CoreMedia"),
                .linkedFramework("CoreText"),
                .linkedFramework("Metal"),
                .linkedFramework("Security"),
                .linkedFramework("VideoToolbox"),
                .linkedLibrary("bz2"),
                .linkedLibrary("iconv"),
                .linkedLibrary("expat"),
                .linkedLibrary("resolv"),
                .linkedLibrary("xml2"),
                .linkedLibrary("z"),
                .linkedLibrary("c++"),
            ]
        ),

        //AUTO_GENERATE_TARGETS_BEGIN//

        .binaryTarget(
            name: "Libunibreak",
            url: "https://github.com/mpvkit/libass-build/releases/download/0.17.4/Libunibreak.xcframework.zip",
            checksum: "001087c0e927ae00f604422b539898b81eb77230ea7700597b70393cd51e946c"
        ),

        .binaryTarget(
            name: "Libfreetype",
            url: "https://github.com/mpvkit/libass-build/releases/download/0.17.4/Libfreetype.xcframework.zip",
            checksum: "f2840aba1ce35e51c0595557eee82c908dac8e32108ecc0661301c06061e051c"
        ),

        .binaryTarget(
            name: "Libfribidi",
            url: "https://github.com/mpvkit/libass-build/releases/download/0.17.4/Libfribidi.xcframework.zip",
            checksum: "4a55513792ef7a17893875f74cc84c56f3657e8768c07a7a96f563a11dc4b743"
        ),

        .binaryTarget(
            name: "Libharfbuzz",
            url: "https://github.com/mpvkit/libass-build/releases/download/0.17.4/Libharfbuzz.xcframework.zip",
            checksum: "91558d8497d9d97bc11eeef8b744d104315893bfee8f17483d8002e14565f84b"
        ),

        .binaryTarget(
            name: "Libass",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libass-994f0b303c7b.xcframework.zip",
            checksum: "430285daf87f999784bdc42946b0ee4f4c3dac0c0f7617ce32a238cb93726de0"
        ),

        .binaryTarget(
            name: "Libbluray",
            url: "https://github.com/mpvkit/libbluray-build/releases/download/1.4.0/Libbluray.xcframework.zip",
            checksum: "bc037d34e2b0b5ab7f202fb371f5fb298136cc66fdf406c2172185d06f53f18d"
        ),

        .binaryTarget(
            name: "Libcrypto",
            url: "https://github.com/mpvkit/openssl-build/releases/download/3.3.5/Libcrypto.xcframework.zip",
            checksum: "593283be2a90f7fd66f6e6ed331b2f099cf403e0926fe3b4ac09a7062b793965"
        ),
        .binaryTarget(
            name: "Libssl",
            url: "https://github.com/mpvkit/openssl-build/releases/download/3.3.5/Libssl.xcframework.zip",
            checksum: "ff5ffd43d015d7285fd37e4a3145b25cbd8d2842740bd629a711c299a20e226a"
        ),

        .binaryTarget(
            name: "Libuavs3d",
            url: "https://github.com/mpvkit/libuavs3d-build/releases/download/1.2.1-fix/Libuavs3d.xcframework.zip",
            checksum: "bd5256081486d16c51c868d755bf70266c424b54c895269580de44ec6707f789"
        ),

        .binaryTarget(
            name: "Libdovi",
            url: "https://github.com/mpvkit/libdovi-build/releases/download/3.3.2/Libdovi.xcframework.zip",
            checksum: "e693e239808350868e79c5448ef9f02e2716bc822dd8632a41a368a1eae5ca7d"
        ),

        .binaryTarget(
            name: "MoltenVK",
            url: "https://github.com/mpvkit/moltenvk-build/releases/download/1.4.1/MoltenVK.xcframework.zip",
            checksum: "9bd1ca1e4563bacd25d6e55d37b10341d50b2601bc2684bc332188e79daa2b79"
        ),

        .binaryTarget(
            name: "Libshaderc_combined",
            url: "https://github.com/mpvkit/libshaderc-build/releases/download/2025.5.0/Libshaderc_combined.xcframework.zip",
            checksum: "758047b615708575b580eb960a2d083f760a29dc462d6eaa360416c946ce433b"
        ),

        .binaryTarget(
            name: "lcms2",
            url: "https://github.com/mpvkit/lcms2-build/releases/download/2.17.0/lcms2.xcframework.zip",
            checksum: "dc0dce0606f6ab6841a8ec5a6bd4448e2f3ef00661a050460f806c9393dc6982"
        ),

        .binaryTarget(
            name: "Libplacebo",
            url: "https://github.com/mpvkit/libplacebo-build/releases/download/7.351.0-2512/Libplacebo.xcframework.zip",
            checksum: "3b2bd57b82549566963effadf0891a141448d9f89c7d48fca0b8f823b854bac6"
        ),

        .binaryTarget(
            name: "Libdav1d",
            url: "https://github.com/edde746/libdav1d-build/releases/download/1.5.3-neon/Libdav1d.xcframework.zip",
            checksum: "7965ecf274af5448fa830bc1fec4e78257cf1d7509ed1cd95e32023b7bdff965"
        ),

        .binaryTarget(
            name: "Libavcodec",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libavcodec-386e90033cc1.xcframework.zip",
            checksum: "d17b251b9d6f247541a97bc27b8885d7607187b92c5cac884f28899d0b210dbc"
        ),
        .binaryTarget(
            name: "Libavdevice",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libavdevice-386e90033cc1.xcframework.zip",
            checksum: "9c789981a0944367036a094410bfbf51ab80197adae42bb26cc69a5fdec5a3d8"
        ),
        .binaryTarget(
            name: "Libavformat",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libavformat-386e90033cc1.xcframework.zip",
            checksum: "fb67161311bc23c98fca536291d31f5f8bbfcfdb0cadc91015a7c9f9f9d87cb3"
        ),
        .binaryTarget(
            name: "Libavfilter",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libavfilter-386e90033cc1.xcframework.zip",
            checksum: "e7de4fb9dbf1da8c33a54c3f19561eab4375c763a2a2200d8e235e0ea64c5e79"
        ),
        .binaryTarget(
            name: "Libavutil",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libavutil-386e90033cc1.xcframework.zip",
            checksum: "0f6ad7578d7fdbfa0ab3c86a09ced6887b02723dc2fd2d653c4716327daf07af"
        ),
        .binaryTarget(
            name: "Libswresample",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libswresample-386e90033cc1.xcframework.zip",
            checksum: "5440f91bc8e5cac7f1d7c2670a4d9cbb04476a0f64da161e3f0d24c7737b1415"
        ),
        .binaryTarget(
            name: "Libswscale",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libswscale-386e90033cc1.xcframework.zip",
            checksum: "961ed603c80fa3e78263299ab2dc9ebbd3623c9a6e63620c7c28ab9ace278f0c"
        ),

        .binaryTarget(
            name: "Libuchardet",
            url: "https://github.com/mpvkit/libuchardet-build/releases/download/0.0.8-xcode/Libuchardet.xcframework.zip",
            checksum: "503202caa0dafb6996b2443f53408a713b49f6c2d4a26d7856fd6143513a50d7"
        ),

        .binaryTarget(
            name: "Libluajit",
            url: "https://github.com/mpvkit/libluajit-build/releases/download/2.1.0-xcode/Libluajit.xcframework.zip",
            checksum: "8e76f267ee100ff5f3bbde7641b2240566df722241cdf8e135be7ef3d29e237a"
        ),

        .binaryTarget(
            name: "Libmpv",
            url: "https://github.com/snapetech-org/mpv-build/releases/download/binaries-apple/Libmpv-7f7e20c706d4.xcframework.zip",
            checksum: "96522ab984b799f11cd080c4eb060ec43452d058e9071c7e4eec41b01c4ffed6"
        ),
        //AUTO_GENERATE_TARGETS_END//
    ]
)
