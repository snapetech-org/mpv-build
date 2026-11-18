import Foundation

do {
    let options = try ArgumentOptions.parse(CommandLine.arguments)
    // Pins live in versions.json at the repository root; load them before
    // performCommand() changes the working directory to dist/.
    try Versions.load()
    try Build.performCommand(options)

    // Dependency order matters: every library links against the ones before it.
    // `ZipBaseBuild` is a concrete class whose only parameter is the library, so
    // the prebuilt-download libraries need no named subclass.
    let builds: [BaseBuild] = [
        // libass
        ZipBaseBuild(library: .libunibreak),
        ZipBaseBuild(library: .libfreetype),
        ZipBaseBuild(library: .libfribidi),
        ZipBaseBuild(library: .libharfbuzz),
        BuildASS(),

        // libbluray
        ZipBaseBuild(library: .libbluray),

        // ffmpeg
        ZipBaseBuild(library: .openssl),
        ZipBaseBuild(library: .libuavs3d),
        BuildXEVD(),
        BuildDAVS2(),
        BuildDAV2D(),
        BuildLCEVC(),
        ZipBaseBuild(library: .libdovi),
        BuildVulkan(),
        ZipBaseBuild(library: .libshaderc),
        ZipBaseBuild(library: .lcms2),
        BuildJPEGXL(),
        ZipBaseBuild(library: .libplacebo),
        ZipBaseBuild(library: .libdav1d),
        BuildFFMPEG(),

        // mpv
        ZipBaseBuild(library: .libuchardet),
        ZipBaseBuild(library: .libluajit),
        BuildMPV(),
    ]

    if !options.libs.isEmpty {
        print("libs=\(options.libs.map(\.rawValue).joined(separator: ",")): only these libraries are compiled from source")
    }
    if options.usePrebuilt {
        print("use-prebuilt: self-built libraries outside libs= are restored from artifacts.json when it covers them")
    }

    // No library is ever skipped: `buildALL()` restores it from the manifest when that is
    // possible and compiles it otherwise, so an unlisted, unpublished library still builds.
    for build in builds {
        try build.buildALL()
    }
} catch {
    print(error.localizedDescription)
    exit(1)
}

/// One component entry of `versions.json`. Unknown keys (platforms, overrides,
/// provenance, ...) are ignored here: the Swift driver only consumes the pins
/// it clones or downloads from.
struct ComponentPin: Decodable {
    let kind: String
    let version: String
    let url: String
    let sha256: String?
    let ref: String?
    let commit: String?
}

/// Reader for the repository-root `versions.json`, the single source of truth
/// for every component's version and acquisition URL across all platform
/// drivers. Loaded once at tool startup, while the working directory is still
/// the repository root.
enum Versions {
    private struct Root: Decodable {
        let formatVersion: Int
        let components: [String: ComponentPin]
    }

    private static var components: [String: ComponentPin] = [:]

    static func load(from url: URL = URL.currentDirectory + "versions.json") throws {
        let data = try Data(contentsOf: url)
        components = try JSONDecoder().decode(Root.self, from: data).components
    }

    static func pin(_ name: String) -> ComponentPin {
        guard let pin = components[name] else {
            fatalError("versions.json has no component named \(name)")
        }
        return pin
    }
}

enum Library: String, CaseIterable {
    case libmpv, FFmpeg, libshaderc, vulkan, lcms2, libdovi, openssl, libunibreak, libfreetype,
        libfribidi, libharfbuzz, libass, libplacebo, libdav1d, libuchardet, libbluray, libluajit,
        libuavs3d, libxevd, libdav2d, libdavs2, liblcevcdec, libjxl

    /// Component name in `versions.json` and `patches/`. The only mapping
    /// between Swift raw values and canonical component names.
    var canonicalName: String {
        switch self {
        case .libmpv:
            return "mpv"
        case .FFmpeg:
            return "ffmpeg"
        case .libxevd:
            return "xevd"
        case .libdav2d:
            return "dav2d"
        case .libdavs2:
            return "davs2"
        case .liblcevcdec:
            return "lcevc_dec"
        default:
            return rawValue.lowercased()
        }
    }

    var version: String {
        Versions.pin(canonicalName).version
    }

    var url: String {
        Versions.pin(canonicalName).url
    }

    var ref: String {
        Versions.pin(canonicalName).ref ?? version
    }

    var commit: String? {
        Versions.pin(canonicalName).commit
    }

    /// The xcframework names this library publishes, in the order `Package.swift`
    /// lists them. `artifacts.json` keys its framework entries by these names, and
    /// a prebuilt restore is only taken when every one of them is present.
    var frameworks: [String] {
        switch self {
        case .libmpv:
            return ["Libmpv"]
        case .FFmpeg:
            return [
                "Libavcodec", "Libavdevice", "Libavformat", "Libavfilter", "Libavutil",
                "Libswresample", "Libswscale",
            ]
        case .openssl:
            return ["Libcrypto", "Libssl"]
        case .libass:
            return ["Libass"]
        case .libunibreak:
            return ["Libunibreak"]
        case .libfreetype:
            return ["Libfreetype"]
        case .libfribidi:
            return ["Libfribidi"]
        case .libharfbuzz:
            return ["Libharfbuzz"]
        case .lcms2:
            return ["lcms2"]
        case .libplacebo:
            return ["Libplacebo"]
        case .libdav1d:
            return ["Libdav1d"]
        case .libdovi:
            return ["Libdovi"]
        case .vulkan:
            return ["MoltenVK"]
        case .libshaderc:
            return ["Libshaderc_combined"]
        case .libuchardet:
            return ["Libuchardet"]
        case .libbluray:
            return ["Libbluray"]
        case .libluajit:
            return ["Libluajit"]
        case .libuavs3d:
            return ["Libuavs3d"]
        case .libxevd:
            // Apple folds XEVD into Libavcodec, so consumers do not need a
            // separately published binary target for this private dependency.
            return []
        case .libdav2d, .liblcevcdec, .libjxl:
            return []
        case .libdavs2:
            // Apple folds davs2 into Libavcodec for the same reason.
            return []
        }
    }
}

private class BuildMPV: BaseBuild {
    init() {
        super.init(library: .libmpv)
    }

    private func spatialTarget(platform: PlatformType, arch: ArchType) -> String? {
        switch (platform, arch) {
        case (.ios, .arm64): return "aarch64-apple-ios"
        case (.isimulator, .arm64): return "aarch64-apple-ios-sim"
        case (.isimulator, .x86_64): return "x86_64-apple-ios"
        case (.tvos, .arm64): return "aarch64-apple-tvos"
        case (.tvsimulator, .arm64): return "aarch64-apple-tvos-sim"
        // macOS includes LuaJIT; adding Rust exceeds its unwind personality limit.
        default: return nil // macOS, Catalyst and unsupported Rust targets keep PCM.
        }
    }

    private func spatialDirectory(platform: PlatformType, arch: ArchType) -> URL {
        scratch(platform: platform, arch: arch) + "spatial"
    }

    override func environment(platform: PlatformType, arch: ArchType) -> [String: String] {
        var environment = super.environment(platform: platform, arch: arch)
        if spatialTarget(platform: platform, arch: arch) != nil {
            environment["PKG_CONFIG_LIBDIR"] = (spatialDirectory(platform: platform, arch: arch) + "pkgconfig").path
                + ":" + (environment["PKG_CONFIG_LIBDIR"] ?? "")
        }
        return environment
    }

    override func build(platform: PlatformType, arch: ArchType) throws {
        let spatial = spatialDirectory(platform: platform, arch: arch)
        if let target = spatialTarget(platform: platform, arch: arch) {
            // Carry the job's Cargo and Rustup locations into the child environment.
            let rust = ProcessInfo.processInfo.environment.filter { ["CARGO_HOME", "RUSTUP_HOME"].contains($0.key) }
            try Utility.launch(path: "python3", arguments: [
                (URL.currentDirectory + "../scripts/build_spatial.py").path,
                "--source", (URL.currentDirectory + "SpatialAudioBridge-\(Versions.pin("spatialaudiobridge").commit!)").path,
                "--output", spatial.path, "--mpv", directoryURL.path,
                "--target", platform.deploymentTarget(arch), "--sdk", platform.isysroot,
                "--rust-target", target,
            ], environment: rust)
        }
        try super.build(platform: platform, arch: arch)
        if spatialTarget(platform: platform, arch: arch) != nil {
            let library = thinDir(platform: platform, arch: arch) + "lib/libmpv.a"
            let combined = spatial + "libmpv.a"
            try Utility.launch(path: "/usr/bin/libtool", arguments: [
                "-static", "-o", combined.path, library.path,
                (spatial + "libmpv_spatial.a").path, (spatial + "libspatial_audio_core.a").path,
            ], environment: ["ZERO_AR_DATE": "1"])
            try FileManager.default.removeItem(at: library)
            try FileManager.default.moveItem(at: combined, to: library)
            let notices = thinDir(platform: platform, arch: arch) + "share/licenses/SpatialAudioBridge"
            try FileManager.default.createDirectory(at: notices, withIntermediateDirectories: true)
            try FileManager.default.copyItem(at: spatial + "ThirdPartyNotices.txt", to: notices + "ThirdPartyNotices.txt")
            // The private libraries are now inside libmpv.a; installed clients
            // must not need the build-only pkg-config dependency.
            let pkgConfig = thinDir(platform: platform, arch: arch) + "lib/pkgconfig/mpv.pc"
            let swiftCompiler = try Utility.launch(path: "/usr/bin/xcrun", arguments: ["--find", "swiftc"], isOutput: true)
            let swiftToolchain = URL(fileURLWithPath: swiftCompiler)
                .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            let swiftLinkFlags = " -L\"${swift_toolchain}/usr/lib/swift/\(platform.sdk.lowercased())\""
                + " -L/usr/lib/swift -framework Accelerate"
            let text = try String(contentsOf: pkgConfig, encoding: .utf8)
            let lines = text.components(separatedBy: "\n").map { line in
                if line.hasPrefix("Libs.private:") {
                    return line + swiftLinkFlags
                }
                guard line.hasPrefix("Requires:") || line.hasPrefix("Requires.private:"),
                      let colon = line.firstIndex(of: ":") else { return line }
                let dependencies = line[line.index(after: colon)...].components(separatedBy: ",")
                    .map { $0.trimmingCharacters(in: .whitespaces) }
                    .filter { $0 != "mpv-spatial" }
                return String(line[...colon]) + " " + dependencies.joined(separator: ", ")
            }
            let extra = lines.contains { $0.hasPrefix("Libs.private:") }
                ? "" : "Libs.private:" + swiftLinkFlags + "\n"
            try ("swift_toolchain=\(swiftToolchain.path)\n" + lines.joined(separator: "\n") + extra)
                .write(to: pkgConfig, atomically: true, encoding: .utf8)
        }
    }

    override func createFramework(framework: String, platform: PlatformType) throws -> String? {
        guard let path = try super.createFramework(framework: framework, platform: platform) else { return nil }
        let notices = spatialDirectory(platform: platform, arch: .arm64) + "ThirdPartyNotices.txt"
        if FileManager.default.fileExists(atPath: notices.path) {
            try FileManager.default.copyItem(at: notices, to: URL(fileURLWithPath: path) + "LICENSE.SpatialAudioBridge")
        }
        return path
    }

    override func packagePkgConfigRelease() throws {
        try super.packagePkgConfigRelease()
        // This hook runs after the release tree is created, before it is zipped.
        for platform in BaseBuild.platforms {
            for arch in architectures(platform) where spatialTarget(platform: platform, arch: arch) != nil {
                let pkgConfig = URL.currentDirectory
                    + ["release/libmpv/pkgconfig-example", platform.rawValue, arch.rawValue, "mpv.pc"]
                let text = try String(contentsOf: pkgConfig, encoding: .utf8)
                // Consumers select their toolchain; never distribute the builder's Xcode path.
                try text.replacingOccurrences(of: "(?m)^swift_toolchain=.*$",
                    with: "swift_toolchain=/path/to/Swift.xctoolchain", options: .regularExpression)
                    .write(to: pkgConfig, atomically: true, encoding: .utf8)
            }
        }
        for platform in BaseBuild.platforms {
            let notices = spatialDirectory(platform: platform, arch: .arm64) + "ThirdPartyNotices.txt"
            if FileManager.default.fileExists(atPath: notices.path) {
                try FileManager.default.copyItem(at: notices,
                    to: URL.currentDirectory + "release/libmpv/LICENSE.SpatialAudioBridge")
                break
            }
        }
    }

    override func arguments(platform: PlatformType, arch: ArchType) -> [String] {
        var array = [
            "-Dlibmpv=true",
            // No __DATE__/__TIME__ stamp: a rebuild of a published content key
            // has to reproduce its bytes (keys.py publish-assets checks). The
            // android and linux drivers pass the same flag.
            "-Dbuild-date=false",
            "-Dgl=enabled",
            "-Dplain-gl=enabled",
            "-Diconv=enabled",
            "-Duchardet=enabled",
            "-Dvulkan=enabled",
            "-Dmoltenvk=enabled",  // from patch option

            "-Djavascript=disabled",
            "-Dzimg=disabled",
            "-Djpeg=disabled",
            "-Dvapoursynth=disabled",
            "-Drubberband=disabled",
        ]
        array.append("-Dgpl=true")
        array.append("-Dspatial-audio=\(spatialTarget(platform: platform, arch: arch) == nil ? "disabled" : "enabled")")
        let blurayLibPath =
            URL.currentDirectory + [
                Library.libbluray.rawValue, platform.rawValue, "thin", arch.rawValue,
            ]
        if FileManager.default.fileExists(atPath: blurayLibPath.path) {
            array.append("-Dlibbluray=enabled")
        } else {
            array.append("-Dlibbluray=disabled")
        }
        if !(platform == .macos && arch.executable) {
            array.append("-Dcplayer=false")
        }
        if platform == .macos {
            array.append(
                "-Dswift-flags=-sdk \(platform.isysroot) -target \(platform.deploymentTarget(arch))"
            )
            array.append("-Dcocoa=enabled")
            array.append("-Dcoreaudio=enabled")
            array.append("-Davfoundation=enabled")
            array.append("-Dvo-avfoundation=enabled")
            array.append("-Dgl-cocoa=enabled")
            array.append("-Dvideotoolbox-gl=enabled")
            array.append("-Dvideotoolbox-pl=enabled")
            array.append("-Dmacos-touchbar=disabled")
            array.append("-Dmacos-media-player=disabled")
            array.append("-Dlua=luajit")
        } else {
            array.append("-Dvideotoolbox-gl=disabled")
            array.append("-Dvideotoolbox-pl=enabled")
            array.append("-Dswift-build=disabled")
            array.append("-Daudiounit=enabled")
            array.append("-Davfoundation=enabled")
            array.append("-Dvo-avfoundation=enabled")
            array.append("-Dlua=disabled")
            if platform == .maccatalyst {
                array.append("-Dcocoa=disabled")
                array.append("-Dcoreaudio=disabled")
            } else {
                array.append("-Dios-gl=enabled")
            }
        }
        return array
    }

}

private class BuildLCEVC: BaseBuild {
    init() {
        super.init(library: .liblcevcdec)
    }

    override func frameworks() throws -> [String] { [] }

    override func build(platform: PlatformType, arch: ArchType) throws {
        let buildURL = scratch(platform: platform, arch: arch)
        let prefix = thinDir(platform: platform, arch: arch)
        let environ = environment(platform: platform, arch: arch)
        let cmake = Utility.shell("which cmake", isOutput: true)!
        let targetPlatform: String
        switch platform {
        case .ios, .isimulator, .maccatalyst: targetPlatform = "iOS"
        case .tvos, .tvsimulator: targetPlatform = "tvOS"
        default: targetPlatform = "macOS"
        }
        try Utility.launch(path: cmake, arguments: [
            "-S", directoryURL.path, "-B", buildURL.path, "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_INSTALL_PREFIX=\(prefix.path)",
            "-DCMAKE_INSTALL_LIBDIR=lib", "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
            "-DCMAKE_SYSTEM_NAME=Darwin", "-DCMAKE_SYSTEM_PROCESSOR=\(arch.cpuFamily)",
            "-DCMAKE_OSX_ARCHITECTURES=\(arch.rawValue)",
            "-DCMAKE_OSX_SYSROOT=\(platform.isysroot)",
            "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
            "-DTARGET_PLATFORM=\(targetPlatform)", "-DBUILD_SHARED_LIBS=OFF",
            "-DVN_SDK_EXECUTABLES=OFF", "-DVN_SDK_UNIT_TESTS=OFF",
            "-DVN_SDK_SAMPLE_SOURCE=OFF", "-DVN_SDK_JSON_CONFIG=OFF",
            "-DVN_SDK_DOCS=OFF", "-DVN_SDK_BUILD_DETAILS=OFF",
            "-DVN_SDK_TRACING=OFF", "-DVN_SDK_METRICS=OFF",
        ], currentDirectoryURL: directoryURL, environment: environ)
        for arguments in [["--build", buildURL.path, "-j8"], ["--install", buildURL.path]] {
            try Utility.launch(path: cmake, arguments: arguments,
                               currentDirectoryURL: directoryURL, environment: environ)
        }
        let python = Utility.shell("which python3", isOutput: true)!
        try Utility.launch(path: python, arguments: [
            (URL.currentDirectory + ["..", "scripts", "fix_lcevc_pkgconfig.py"]).path,
            (prefix + ["lib", "pkgconfig", "lcevc_dec.pc"]).path, "--runtime", "c++",
        ], environment: environ)
        try Utility.launch(path: python, arguments: [
            (URL.currentDirectory + ["..", "scripts", "stage_decoder_notices.py"]).path,
            directoryURL.path, prefix.path, "lcevc_dec",
        ], environment: environ)
    }
}

private class BuildJPEGXL: BaseBuild {
    init() {
        super.init(library: .libjxl)
    }

    override func frameworks() throws -> [String] { [] }

    override func build(platform: PlatformType, arch: ArchType) throws {
        let prefix = thinDir(platform: platform, arch: arch)
        try FileManager.default.createDirectory(at: prefix, withIntermediateDirectories: true)
        var env = environment(platform: platform, arch: arch)
        env["BUILD_SUFFIX"] = "-\(platform.rawValue)-\(arch.rawValue)"
        env["JXL_LCMS2_PREFIX"] = thinDir(library: .lcms2, platform: platform, arch: arch).path
        try Utility.launch(path: "/bin/bash", arguments: [
            (URL.currentDirectory + ["..", "scripts", "build_jpegxl.sh"]).path,
            directoryURL.path, prefix.path, "8",
            "-DCMAKE_SYSTEM_NAME=Darwin", "-DCMAKE_SYSTEM_PROCESSOR=\(arch.cpuFamily)",
            "-DCMAKE_OSX_ARCHITECTURES=\(arch.rawValue)", "-DCMAKE_OSX_SYSROOT=\(platform.isysroot)",
            "-DCMAKE_C_COMPILER_TARGET=\(platform.deploymentTarget(arch))",
            "-DCMAKE_CXX_COMPILER_TARGET=\(platform.deploymentTarget(arch))",
            "-DCMAKE_MACOSX_RPATH=ON",
        ], currentDirectoryURL: directoryURL, environment: env)
    }
}

private class BuildXEVD: BaseBuild {
    init() {
        super.init(library: .libxevd)
    }

    override func frameworks() throws -> [String] {
        // The archive is merged into FFmpeg's libavcodec before packaging.
        return []
    }

    override func build(platform: PlatformType, arch: ArchType) throws {
        let buildURL = scratch(platform: platform, arch: arch)
        try? FileManager.default.removeItem(at: buildURL)
        try FileManager.default.createDirectory(at: buildURL, withIntermediateDirectories: true)

        let prefix = thinDir(platform: platform, arch: arch)
        let environ = environment(platform: platform, arch: arch)
        let cmake = Utility.shell("which cmake", isOutput: true)!
        try Utility.launch(
            path: cmake,
            arguments: [
                "-S", directoryURL.path,
                "-B", buildURL.path,
                "-G", "Ninja",
                "-DCMAKE_BUILD_TYPE=Release",
                "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DCMAKE_INSTALL_PREFIX=\(prefix.path)",
                "-DCMAKE_INSTALL_LIBDIR=lib",
                "-DCMAKE_SYSTEM_NAME=Darwin",
                "-DCMAKE_OSX_ARCHITECTURES=\(arch.rawValue)",
                "-DCMAKE_SYSTEM_PROCESSOR=\(arch.cpuFamily)",
                "-DARM=\(arch.cpuFamily == "aarch64" ? "TRUE" : "FALSE")",
                "-DSET_PROF=MAIN",
            ],
            currentDirectoryURL: directoryURL,
            environment: environ
        )

        let ninja = Utility.shell("which ninja", isOutput: true)!
        try Utility.launch(
            path: ninja,
            arguments: ["-C", buildURL.path, "-j8", "xevd"],
            currentDirectoryURL: directoryURL,
            environment: environ
        )

        let libraryDirectory = prefix + "lib"
        let includeDirectory = prefix + "include"
        let pkgConfigDirectory = libraryDirectory + ["pkgconfig"]
        try FileManager.default.createDirectory(at: libraryDirectory, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: includeDirectory, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: pkgConfigDirectory, withIntermediateDirectories: true)
        try FileManager.default.copyItem(
            at: buildURL + ["src_main", "libxevd.a"],
            to: libraryDirectory + "libxevd.a"
        )
        try FileManager.default.copyItem(at: directoryURL + ["inc", "xevd.h"], to: includeDirectory + "xevd.h")
        try FileManager.default.copyItem(
            at: buildURL + "xevd_exports.h",
            to: includeDirectory + "xevd_exports.h"
        )

        let descriptor = """
        prefix=\(prefix.path)
        exec_prefix=${prefix}
        libdir=${exec_prefix}/lib
        includedir=${prefix}/include
        Name: xevd
        Description: MPEG-5 EVC decoder (Main and Baseline)
        Version: \(library.version)
        Libs: -L${libdir} -lxevd
        Libs.private: -lm
        Cflags: -I${includedir}
        """
        try descriptor.write(
            to: pkgConfigDirectory + "xevd.pc",
            atomically: true,
            encoding: .utf8
        )
    }
}

private class BuildDAV2D: BaseBuild {
    init() { super.init(library: .libdav2d) }

    override func frameworks() throws -> [String] { [] }

    override func arguments(platform: PlatformType, arch: ArchType) -> [String] {
        ["--libdir=lib", "-Denable_tools=false", "-Denable_tests=false", "-Denable_asm=false"]
    }
}

private class BuildDAVS2: BaseBuild {
    init() {
        super.init(library: .libdavs2)
    }

    override func frameworks() throws -> [String] {
        // The archive is merged into FFmpeg's libavcodec before packaging.
        return []
    }

    override func build(platform: PlatformType, arch: ArchType) throws {
        let buildURL = scratch(platform: platform, arch: arch)
        try? FileManager.default.removeItem(at: buildURL)
        try FileManager.default.createDirectory(at: buildURL, withIntermediateDirectories: true)
        let sourceURL = buildURL + "source"
        try FileManager.default.copyItem(at: directoryURL, to: sourceURL)
        try? FileManager.default.removeItem(at: sourceURL + ".git")

        let prefix = thinDir(platform: platform, arch: arch)
        let environment = self.environment(platform: platform, arch: arch)
        var crossEnvironment = environment
        crossEnvironment["CC"] = environment["CXX"]
        let hostArch = arch.cpuFamily == "aarch64" ? "aarch64" : arch.cpuFamily
        let host = "\(hostArch)-apple-darwin"
        let configureDirectory = sourceURL + ["build", "linux"]
        try Utility.launch(
            path: "/bin/bash",
            arguments: [
                (configureDirectory + "configure").path,
                "--host=\(host)",
                "--prefix=\(prefix.path)",
                "--enable-pic",
                "--disable-cli",
                "--disable-asm",
                "--bit-depth=10",
                "--chroma-format=all",
            ],
            currentDirectoryURL: configureDirectory,
            environment: crossEnvironment
        )
        // configure creates source/version.h; normalize only after it exists.
        try Utility.launch(
            path: "/usr/bin/sed",
            arguments: [
                "-i", "", "-E",
                "s/(#define XBUILD_TIME[[:space:]]+)\"[^\"]*\"/\\1\"2020-01-01 00:00:00\"/",
                (sourceURL + ["source", "version.h"]).path,
            ],
            currentDirectoryURL: sourceURL
        )
        try Utility.launch(
            path: "/usr/bin/make",
            arguments: ["-j8"],
            currentDirectoryURL: configureDirectory,
            environment: crossEnvironment
        )
        try Utility.launch(
            path: "/usr/bin/make",
            arguments: ["install"],
            currentDirectoryURL: configureDirectory,
            environment: crossEnvironment
        )
        try Utility.launch(
            path: "/usr/bin/sed",
            arguments: [
                "-i", "", "-E",
                "s/^Version: ([0-9]+\\.[0-9]+)\\.$/Version: \\1.0/",
                (prefix + ["lib", "pkgconfig", "davs2.pc"]).path,
            ],
            currentDirectoryURL: sourceURL
        )
    }
}

private class BuildFFMPEG: BaseBuild {
    init() {
        super.init(library: .FFmpeg)
    }

    override func beforeBuild() throws {
        try super.beforeBuild()

        let lldbFile = URL.currentDirectory + "LLDBInitFile"
        try? FileManager.default.removeItem(at: lldbFile)
        FileManager.default.createFile(atPath: lldbFile.path, contents: nil, attributes: nil)
        let path = directoryURL + "libavcodec/videotoolbox.c"
        if let data = FileManager.default.contents(atPath: path.path), var str = String(data: data, encoding: .utf8) {
            str = str.replacingOccurrences(of: "kCVPixelBufferOpenGLESCompatibilityKey", with: "kCVPixelBufferMetalCompatibilityKey")
            str = str.replacingOccurrences(of: "kCVPixelBufferIOSurfaceOpenGLTextureCompatibilityKey", with: "kCVPixelBufferMetalCompatibilityKey")
            try? str.write(toFile: path.path, atomically: true, encoding: .utf8)
        }
    }

    override func flagsDependencelibrarys() -> [Library] {
        // LCEVC consists of multiple archives; its pkg-config descriptor
        // supplies them. The generic flag builder would invent -llcevcdec.
        [.libdovi, .libxevd, .libdavs2]
    }

    override func frameworks() throws -> [String] {
        var frameworks: [String] = []
        if let platform = platforms().first {
            if let arch = platform.architectures.first {
                let lib = thinDir(platform: platform, arch: arch) + "lib"
                let fileNames = try FileManager.default.contentsOfDirectory(atPath: lib.path)
                for fileName in fileNames {
                    if fileName.hasPrefix("lib"), fileName.hasSuffix(".a") {
                        // 因为其他库也可能引入libavformat,所以把lib改成大写，这样就可以排在前面，覆盖别的库。
                        frameworks.append("Lib" + fileName.dropFirst(3).dropLast(2))
                    }
                }
            }
        }
        return frameworks
    }

    override func build(platform: PlatformType, arch: ArchType) throws {
        try super.build(platform: platform, arch: arch)
        let buildURL = scratch(platform: platform, arch: arch)
        let prefix = thinDir(platform: platform, arch: arch)

        // FFmpeg's libavcodec references XEVD and davs2 symbols. Merge both
        // pinned archives into libavcodec so the published SwiftPM framework
        // stays self-contained without separate decoder targets.
        let codecArchive = prefix + ["lib", "libavcodec.a"]
        let xevdArchive = thinDir(library: .libxevd, platform: platform, arch: arch)
            + ["lib", "libxevd.a"]
        let davs2Archive = thinDir(library: .libdavs2, platform: platform, arch: arch)
            + ["lib", "libdavs2.a"]
        let dav2dArchive = thinDir(library: .libdav2d, platform: platform, arch: arch)
            + ["lib", "libdav2d.a"]
        let sdkPrefix = thinDir(library: .liblcevcdec, platform: platform, arch: arch)
        let sdkArchives = ["api", "api_utility", "pipeline_cpu", "pipeline", "enhancement",
                           "pixel_processing", "common", "extract"].map {
            sdkPrefix + ["lib", "liblcevc_dec_\($0).a"]
        }
        let jxlPrefix = thinDir(library: .libjxl, platform: platform, arch: arch)
        let jxlArchives = ["jxl", "jxl_threads", "jxl_cms", "hwy", "brotlienc", "brotlidec", "brotlicommon"].map {
            jxlPrefix + ["lib", "lib\($0).a"]
        }
        for archive in [dav2dArchive] + sdkArchives + jxlArchives {
            guard FileManager.default.fileExists(atPath: archive.path) else {
                throw NSError(domain: "BuildFFMPEG", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "Missing bundled SDK archive: \(archive.path)"])
            }
        }
        let notices = prefix + ["share", "licenses", "pleazyng-codecs"]
        try FileManager.default.createDirectory(at: notices, withIntermediateDirectories: true)
        let python = Utility.shell("which python3", isOutput: true)!
        for dependency in [Library.libxevd, .libdavs2, .libdav2d] {
            try Utility.launch(path: python, arguments: [
                (URL.currentDirectory + ["..", "scripts", "stage_decoder_notices.py"]).path,
                (URL.currentDirectory + "\(dependency.rawValue)-\(dependency.version)").path,
                prefix.path, dependency.canonicalName,
            ])
        }
        for (source, name) in [(sdkPrefix, "lcevc_dec"), (jxlPrefix, "libjxl")] {
            let sourceNotices = source + ["share", "licenses", "pleazyng-codecs", name]
            try? FileManager.default.removeItem(at: notices + name)
            try FileManager.default.copyItem(at: sourceNotices, to: notices + name)
        }
        let mergedArchive = prefix + ["lib", "libavcodec.merged.a"]
        guard FileManager.default.fileExists(atPath: codecArchive.path),
            FileManager.default.fileExists(atPath: xevdArchive.path),
            FileManager.default.fileExists(atPath: davs2Archive.path)
        else {
            throw NSError(
                domain: "BuildFFMPEG",
                code: 1,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "Cannot merge external decoders: expected libavcodec.a, libxevd.a, and libdavs2.a for \(platform.rawValue)/\(arch.rawValue)"
                ]
            )
        }
        try Utility.launch(
            path: "/usr/bin/libtool",
            arguments: [
                "-static", "-o", mergedArchive.path, codecArchive.path,
                xevdArchive.path, davs2Archive.path, dav2dArchive.path,
            ] + (sdkArchives + jxlArchives).map { $0.path },
            currentDirectoryURL: directoryURL,
            environment: environment(platform: platform, arch: arch)
        )
        try FileManager.default.removeItem(at: codecArchive)
        try FileManager.default.moveItem(at: mergedArchive, to: codecArchive)
        if platform == .macos, arch.executable {
            for test in ["test_jpegxl_decode.py", "test_av2_decode.py"] {
                try Utility.launch(path: python, arguments: [
                    (URL.currentDirectory + ["..", "scripts", test]).path,
                    (prefix + ["bin", "ffprobe"]).path,
                ], currentDirectoryURL: directoryURL)
            }
        }

        let lldbFile = URL.currentDirectory + "LLDBInitFile"
        if let data = FileManager.default.contents(atPath: lldbFile.path),
            var str = String(data: data, encoding: .utf8)
        {
            str.append(
                "settings \(str.isEmpty ? "set" : "append") target.source-map \((buildURL + "src").path) \(directoryURL.path)\n"
            )
            try str.write(toFile: lldbFile.path, atomically: true, encoding: .utf8)
        }
        try FileManager.default.copyItem(
            at: buildURL + "config.h", to: prefix + "include/libavutil/config.h")
        try FileManager.default.copyItem(
            at: buildURL + "config.h", to: prefix + "include/libavcodec/config.h")
        try FileManager.default.copyItem(
            at: buildURL + "config.h", to: prefix + "include/libavformat/config.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavutil/getenv_utf8.h",
            to: prefix + "include/libavutil/getenv_utf8.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavutil/libm.h", to: prefix + "include/libavutil/libm.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavutil/thread.h", to: prefix + "include/libavutil/thread.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavutil/intmath.h", to: prefix + "include/libavutil/intmath.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavutil/mem_internal.h",
            to: prefix + "include/libavutil/mem_internal.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavutil/attributes_internal.h",
            to: prefix + "include/libavutil/attributes_internal.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavcodec/mathops.h", to: prefix + "include/libavcodec/mathops.h")
        try FileManager.default.copyItem(
            at: buildURL + "src/libavformat/os_support.h",
            to: prefix + "include/libavformat/os_support.h")
        let internalPath = prefix + "include/libavutil/internal.h"
        try FileManager.default.copyItem(
            at: buildURL + "src/libavutil/internal.h", to: internalPath)
        if let data = FileManager.default.contents(atPath: internalPath.path),
            var str = String(data: data, encoding: .utf8)
        {
            str = str.replacingOccurrences(
                of: """
                    #include "timer.h"
                    """,
                with: """
                    // #include "timer.h"
                    """)
            str = str.replacingOccurrences(
                of: "kCVPixelBufferIOSurfaceOpenGLTextureCompatibilityKey",
                with: "kCVPixelBufferMetalCompatibilityKey")
            try str.write(toFile: internalPath.path, atomically: true, encoding: .utf8)
        }

    }

    override func arguments(platform: PlatformType, arch: ArchType) -> [String] {
        var arguments = ffmpegConfiguers
        if BaseBuild.options.enableDebug {
            arguments.append("--enable-debug")
            arguments.append("--disable-stripping")
            arguments.append("--disable-optimizations")
        } else {
            arguments.append("--disable-debug")
            arguments.append("--enable-stripping")
            arguments.append("--enable-optimizations")
        }
        arguments.append("--enable-gpl")
        arguments.append("--enable-libjxl")
        arguments.append("--enable-libdav2d")
        // arguments += Build.ffmpegConfiguers
        arguments.append("--disable-large-tests")
        arguments.append("--ignore-tests=TESTS")
        arguments.append("--arch=\(arch.cpuFamily)")
        arguments.append("--target-os=darwin")
        // arguments.append(arch.cpu())

        /**
         aacpsdsp.o), building for Mac Catalyst, but linking in object file built for
         x86_64 binaries are built without ASM support, since ASM for x86_64 is actually x86 and that confuses `xcodebuild -create-xcframework` https://stackoverflow.com/questions/58796267/building-for-macos-but-linking-in-object-file-built-for-free-standing/59103419#59103419
         */
        if platform == .maccatalyst || arch == .x86_64 {
            arguments.append("--disable-neon")
            arguments.append("--disable-asm")
        } else {
            arguments.append("--enable-neon")
            arguments.append("--enable-asm")
        }
        if platform == .macos, arch.executable {
            arguments.append("--enable-ffplay")
            arguments.append("--enable-sdl2")
            arguments.append("--enable-decoder=rawvideo")
            arguments.append("--enable-filter=color")
            arguments.append("--enable-filter=lut")
            arguments.append("--enable-filter=testsrc")
        } else {
            arguments.append("--disable-programs")
        }
        //        if platform == .isimulator || platform == .tvsimulator {
        //            arguments.append("--assert-level=1")
        //        }
        // libdovi is what makes Dolby Vision profile 7 conversion possible:
        // patch 0021 registers it with configure and #if CONFIG_LIBDOVI guards
        // the real conversion, so without --enable-libdovi the VideoToolbox
        // path keeps asking for profile 8.1 and always gets ENOSYS back.
        // FFmpeg 9 compiles Vulkan shaders with the host glslang executable;
        // it no longer accepts --enable-libshaderc. Keep the packaged shaderc
        // library for libplacebo/mpv, without passing it as an FFmpeg option.
        let dependencyLibrary = [
            Library.libfreetype, .libharfbuzz, .libfribidi, .libass, .vulkan,
            .lcms2, .libplacebo, .libdav1d, .libdovi, .libuavs3d, .libxevd, .libdavs2, .liblcevcdec,
            .openssl,
        ]
        for library in dependencyLibrary {
            let path =
                URL.currentDirectory + [library.rawValue, platform.rawValue, "thin", arch.rawValue]
            if FileManager.default.fileExists(atPath: path.path) {
                arguments.append(library == .liblcevcdec ? "--enable-liblcevc-dec" : "--enable-\(library.rawValue)")
                if library == .libdav1d || library == .libuavs3d || library == .libxevd
                    || library == .libdavs2
                {
                    arguments.append("--enable-decoder=\(library.rawValue)")
                } else if library == .libass {
                    arguments.append("--enable-filter=ass")
                    arguments.append("--enable-filter=subtitles")
                } else if library == .libplacebo {
                    arguments.append("--enable-filter=libplacebo")
                }
            }
        }

        return arguments
    }

    override func frameworkExcludeHeaders(_ framework: String) -> [String] {
        if framework == "Libavcodec" {
            return ["xvmc", "vdpau", "qsv", "dxva2", "d3d11va", "d3d12va"]
        } else if framework == "Libavutil" {
            return [
                "hwcontext_vulkan", "hwcontext_vdpau", "hwcontext_vaapi", "hwcontext_qsv",
                "hwcontext_opencl", "hwcontext_dxva2", "hwcontext_d3d11va", "hwcontext_d3d12va",
                "hwcontext_cuda",
            ]
        } else {
            return super.frameworkExcludeHeaders(framework)
        }
    }

    private let ffmpegConfiguers = [
        // Configuration options:
        "--disable-armv5te", "--disable-armv6", "--disable-armv6t2",
        "--disable-bzlib", "--disable-gray", "--disable-iconv", "--disable-linux-perf",
        "--disable-shared", "--disable-small", "--disable-symver", "--disable-xlib",
        "--enable-cross-compile", "--enable-libxml2",
        "--enable-optimizations", "--enable-pic", "--enable-runtime-cpudetect", "--enable-static",
        "--enable-thumb", "--enable-version3",
        "--pkg-config-flags=--static",
        // Documentation options:
        "--disable-doc", "--disable-htmlpages", "--disable-manpages", "--disable-podpages",
        "--disable-txtpages",
        // Component options:
        "--enable-avcodec", "--enable-avformat", "--enable-avutil", "--enable-network",
        "--enable-swresample", "--enable-swscale",
        "--disable-securetransport", "--disable-gnutls",
        "--disable-libtls", "--disable-mbedtls",
        "--disable-devices", "--disable-outdevs", "--disable-indevs",
        // ,"--disable-pthreads"
        // ,"--disable-w32threads"
        // ,"--disable-os2threads"
        // ,"--disable-dct"
        // ,"--disable-dwt"
        // ,"--disable-lsp"
        // ,"--disable-lzo"
        // ,"--disable-mdct"
        // ,"--disable-rdft"
        // ,"--disable-fft"
        // Hardware accelerators:
        "--disable-d3d11va", "--disable-d3d12va", "--disable-dxva2", "--disable-vaapi",
        "--disable-vdpau",
        // Individual component options:
        // ,"--disable-everything"
        // ./configure --list-muxers
        "--enable-muxers",
        // ./configure --list-encoders
        "--enable-encoders",
        // ./configure --list-protocols
        "--enable-protocols",
        // ./configure --list-demuxers
        "--enable-demuxers",
        // ./configure --list-bsfs
        "--enable-bsfs",
        // ./configure --list-decoders
        "--enable-decoders",

        // ./configure --list-filters
        "--disable-filters",
        "--enable-filter=crop",
        "--enable-filter=aecho", "--enable-filter=adelay", "--enable-filter=asetpts", "--enable-filter=alimiter",
        "--enable-filter=aspectralstats",
        "--enable-filter=bass",
        "--enable-filter=stereowiden",
        "--enable-filter=treble",

        "--enable-filter=aformat", "--enable-filter=amix", "--enable-filter=anull",
        "--enable-filter=aresample",
        "--enable-filter=areverse", "--enable-filter=asetrate", "--enable-filter=atempo",
        "--enable-filter=atrim",
        "--enable-filter=bwdif", "--enable-filter=decimate", "--enable-filter=delogo",
        "--enable-filter=equalizer", "--enable-filter=estdif",
        "--enable-filter=fieldmatch",
        "--enable-filter=firequalizer", "--enable-filter=format", "--enable-filter=fps",
        "--enable-filter=hflip", "--enable-filter=hwdownload", "--enable-filter=hwmap",
        "--enable-filter=hwupload",
        "--enable-filter=idet", "--enable-filter=lenscorrection", "--enable-filter=lut*",
        "--enable-filter=negate", "--enable-filter=null",
        "--enable-filter=overlay",
        "--enable-filter=palettegen", "--enable-filter=paletteuse", "--enable-filter=pan",
        "--enable-filter=rotate",
        "--enable-filter=scale", "--enable-filter=setpts", "--enable-filter=superequalizer",
        "--enable-filter=transpose", "--enable-filter=trim",
        "--enable-filter=vflip", "--enable-filter=volume", "--enable-filter=loudnorm",
        "--enable-filter=w3fdif",
        "--enable-filter=yadif",
        "--enable-filter=avgblur_vulkan", "--enable-filter=blend_vulkan",
        "--enable-filter=bwdif_vulkan",
        "--enable-filter=chromaber_vulkan", "--enable-filter=flip_vulkan",
        "--enable-filter=gblur_vulkan",
        "--enable-filter=hflip_vulkan", "--enable-filter=nlmeans_vulkan",
        "--enable-filter=overlay_vulkan",
        "--enable-filter=vflip_vulkan", "--enable-filter=xfade_vulkan",
    ]

}

private class BuildASS: BaseBuild {
    init() {
        super.init(library: .libass)
    }

    override func arguments(platform: PlatformType, arch: ArchType) -> [String] {
        // AArch64 asm assembles with clang; x86 asm would need nasm, so keep
        // SIMD to the arm64 slices (mirrors the FFmpeg asm policy).
        let asm = arch == .arm64 || arch == .arm64e
        return [
            "-Dasm=\(asm ? "enabled" : "disabled")",
            "-Dlibunibreak=enabled",
            "-Dcoretext=enabled",
            "-Dfontconfig=disabled",
            "-Ddirectwrite=disabled",
            "-Dcheckasm=disabled",
            "-Dtest=disabled",
            "-Dprofile=disabled",
            "-Dcompare=disabled",
            "-Dfuzz=disabled",
        ]
    }
}

private class BuildVulkan: ZipBaseBuild {
    init() {
        super.init(library: .vulkan)
    }

    /// MoltenVK's `-all.zip` carries the static library inside the xcframework
    /// slice rather than in the shared `lib/<platform>/thin/<arch>/lib` layout.
    override func unpackedThinLib(root: URL, platform: PlatformType, arch: ArchType) -> URL {
        root + ["lib", "MoltenVK.xcframework", platform.frameworkName]
    }
}
