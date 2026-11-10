import Foundation
import AVFoundation
import Libmpv

let layer = AVSampleBufferDisplayLayer()
layer.bounds = CGRect(x: 0, y: 0, width: 640, height: 360)
layer.contentsScale = 1
DispatchQueue.global().async {
    let player = mpv_create()!
    func option(_ name: String, _ value: String) {
        let result = mpv_set_option_string(player, name, value)
        precondition(result >= 0, "\(name): \(result)")
    }
    option("vo", "avfoundation")
    option("avfoundation-presentation", "host")
    option("hwdec", "videotoolbox")
    option("audio", "no")
    option("keep-open", "yes")
    option("loop-file", "inf")
    option("glsl-shaders", CommandLine.arguments[2])
    option("wid", String(Int(bitPattern: Unmanaged.passUnretained(layer).toOpaque())))
    mpv_request_log_messages(player, "info")
    precondition(mpv_initialize(player) >= 0)
    mpv_command_string(player, "loadfile \"\(CommandLine.arguments[1])\"")
    var renders = [String]()
    let start = Date()
    var stretched = false
    while Date().timeIntervalSince(start) < 15 {
        Thread.sleep(forTimeInterval: 0.02)
        while let event = mpv_wait_event(player, 0), event.pointee.event_id != MPV_EVENT_NONE {
            if event.pointee.event_id == MPV_EVENT_LOG_MESSAGE, let data = event.pointee.data {
                let log = data.assumingMemoryBound(to: mpv_event_log_message.self).pointee
                let text = String(cString: log.text!)
                print(String(cString: log.prefix!) + ": " + text, terminator: "")
                if text.contains("User shaders: rendering") { renders.append(text) }
            }
        }
        if !stretched && !renders.isEmpty {
            DispatchQueue.main.sync {
                layer.bounds = CGRect(x: 0, y: 0, width: 640, height: 480)
            }
            precondition(mpv_set_property_string(player, "keepaspect", "no") >= 0)
            stretched = true
        }
        if renders.contains(where: {$0.contains("at 640x480")}) { break }
    }
    mpv_terminate_destroy(player)
    precondition(renders.contains(where: {$0.contains("at 640x360")}), "No initial shader frame rendered")
    precondition(renders.contains(where: {$0.contains("at 640x480")}), "No ambient-style stretched shader frame rendered")
    print("PASS: real GLSL frames rendered at picture and stretched layer sizes")

    DispatchQueue.main.async { exit(0) }
}
DispatchQueue.main.asyncAfter(deadline: .now() + 40) {
    fputs("FAIL: playback lifecycle timed out\n", stderr)
    exit(2)
}
RunLoop.main.run()
