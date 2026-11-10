package com.edde746.mpv

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CompositorOptionsDeviceTest {
    @Test(timeout = 30000)
    fun bundledOptionsInitializeAndChangeThroughJni() {
        val player = MpvPlayer.create(InstrumentationRegistry.getInstrumentation().targetContext, object : MpvPlayer.Listener {}) {
            setOption("vo", "null")
            setOption("vid", "no")
            setOption("ao", "null")
            setOption("vo-mediacodec-letterbox-fill", "no")
            setOption("vo-mediacodec-osd-vsync-delay", "1")
        }
        try {
            assertEquals(false, player.getFlag("options/vo-mediacodec-letterbox-fill"))
            assertEquals(1, player.getInt("options/vo-mediacodec-osd-vsync-delay"))
            player.setProperty("options/vo-mediacodec-letterbox-fill", true)
            player.setProperty("options/vo-mediacodec-osd-vsync-delay", 0)
            assertEquals(true, player.getFlag("options/vo-mediacodec-letterbox-fill"))
            assertEquals(0, player.getInt("options/vo-mediacodec-osd-vsync-delay"))
            try {
                player.setProperty("options/vo-mediacodec-osd-vsync-delay", 4)
                fail("The native delay range must reject 4")
            } catch (_: MpvException) {
                assertEquals(0, player.getInt("options/vo-mediacodec-osd-vsync-delay"))
            }
        } finally {
            player.close()
        }
    }
}
