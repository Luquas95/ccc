package io.github.luquas95.ccc

import com.journeyapps.barcodescanner.CaptureActivity

/**
 * The QR scanner of the pairing screen. The library's own CaptureActivity is declared
 * `sensorLandscape`, which turns the phone's screen; this subclass only exists so the manifest
 * can pin it to portrait (see AndroidManifest.xml).
 */
class PortraitCaptureActivity : CaptureActivity()
