# Etude — App Store release checklist

The app is feature-complete and builds/runs. What's left is shipping logistics —
most of it needs **your** Apple account, a Mac with Xcode, and a physical iPhone.
Work top to bottom.

---

## 1. Accounts & tools
- [ ] **Apple Developer Program** membership ($99/yr) — https://developer.apple.com/programs/
- [ ] Xcode signed in with that Apple ID (Settings → Accounts)
- [ ] A physical iPhone for real-device testing (mic + Core ML can't be fully judged in the Simulator)

## 2. Identity & signing  *(current values are placeholders)*
- [x] Bundle id set to **`com.anay.etude`** in `project.yml`. (You still register this exact id under your account in App Store Connect / the Developer portal.)
- [ ] Confirm the display name. `CFBundleDisplayName` is “Etude” (plain E, chosen for easy typing/search). The **App Store name** must be unique — check availability in App Store Connect; the on-device name can differ from the listing name.
- [ ] In Xcode target → Signing & Capabilities: select your **Team**, enable **Automatic signing**. No special capabilities are required (microphone is granted via the Info.plist string, not an entitlement).
- [ ] Decide device support. The target is currently **iPhone + iPad** (`TARGETED_DEVICE_FAMILY = "1,2"`). If you don't want to make/ship iPad screenshots, set it to `"1"` (iPhone only) in `project.yml`.

## 3. Privacy  *(App Store will reject without these)*
- [ ] **Microphone usage string** — already set: `NSMicrophoneUsageDescription` = “Etude listens to the piano you play so it can check your notes and guide your practice.” Keep it specific.
- [x] **Privacy manifest** — `App/PrivacyInfo.xcprivacy` is created, bundled, and validated (declares no tracking, no collected data, and the `UserDefaults` reason `CA92.1` for `@AppStorage`). Template still below for reference.
- [ ] **App Privacy “nutrition label”** in App Store Connect → set **Data Not Collected**. The app makes no network calls; audio is analysed on-device and never stored or uploaded (say this in review notes too).
- [x] **Export compliance** — `ITSAppUsesNonExemptEncryption = false` is set in `project.yml` and in the built Info.plist, so you skip the per-upload encryption question.

## 4. Assets & presentation
- [ ] **App icon** — 1024×1024 present (`AppIcon`). A single 1024 marketing icon in the asset catalog satisfies current App Store requirements; Xcode derives the rest.
- [ ] **Launch screen** — present (`UILaunchScreen`).
- [x] **iPhone screenshots** — a starter 6.9" set (1320×2868, iPhone 16 Pro Max) is in `ios/screenshots/`: onboarding, main, melody Learn (glowing target), chord Learn. Retake/add more on a real device if you like.
- [ ] **iPad screenshots** — still needed because the target includes iPad. Capture the same views on an iPad simulator, or switch to iPhone-only in `project.yml`.

## 5. Versioning
- [x] `MARKETING_VERSION` = `1.0.0`, `CURRENT_PROJECT_VERSION` = `1` (set). Bump the build number on every upload.

## 6. Test on a real device
- [ ] Mic detection (live Learn/Practice) — talking is ignored, fast playing keeps up.
- [ ] **Record → transcribe** — record a short melody, confirm it becomes a practiceable piece; check Core ML latency is acceptable.
- [ ] **Chord practice** — multi-touch: tap a chord's notes, confirm it submits and grades (this is the one path the Simulator can't exercise).
- [ ] Import a real `.mid` / `.musicxml` / `.mxl` via Files.
- [ ] First-launch onboarding shows once; audio interruptions (calls, other apps) don't crash it.

## 7. Archive & upload
- [ ] In Xcode: select **Any iOS Device (arm64)**, `Product → Archive` (Release config).
- [ ] In the Organizer: **Validate App**, fix any issues, then **Distribute App → App Store Connect → Upload**.

## 8. App Store Connect listing
- [ ] Create the app record (bundle id, name, primary language).
- [ ] **Category**: primary *Music* (or *Education*); it fits both.
- [ ] **Age rating**: 4+.
- [x] Description, subtitle, keywords drafted in **`store-listing.md`** — paste from there. Still add a support URL.
- [ ] Attach screenshots; select the build you uploaded.

## 9. App Review notes  *(paste into “Notes for Review”)*
> Etude is an offline piano practice app.
> • **Microphone**: used only for real-time pitch detection while you practice. Audio is analysed on-device and is **never recorded to disk or sent anywhere**. The “Record” feature transcribes locally via a bundled Core ML model.
> • **No account, no network, no data collection.**
> • **Testing without a piano**: you don't need an instrument — every mode works by **tapping the on-screen keys**, and “Demonstrate” plays the piece for you. Microphone permission can be declined and the app remains fully usable.

## 10. Rejection risks this app already avoids
- Mic permission has a clear, specific purpose string ✅
- No hidden data collection / tracking ✅
- Fully usable without granting the mic permission (tap input) ✅ — Apple rejects apps that are unusable when a permission is denied.
- Real functionality, not a thin wrapper ✅

## 11. After submission
- [ ] Respond quickly to any reviewer questions.
- [ ] On approval, choose manual or automatic release.
- [ ] Plan v1.1: iCloud/Files song library, polyphonic *live* mic (rolling Core ML), rhythm/timing feedback.

---

### Privacy manifest template — `App/PrivacyInfo.xcprivacy`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>NSPrivacyTracking</key><false/>
  <key>NSPrivacyTrackingDomains</key><array/>
  <key>NSPrivacyCollectedDataTypes</key><array/>
  <key>NSPrivacyAccessedAPITypes</key>
  <array>
    <dict>
      <key>NSPrivacyAccessedAPIType</key>
      <string>NSPrivacyAccessedAPICategoryUserDefaults</string>
      <key>NSPrivacyAccessedAPITypeReasons</key>
      <array><string>CA92.1</string></array>
    </dict>
  </array>
</dict>
</plist>
```
Add it under `App/` (it's picked up automatically by the `sources: [App]` glob), then re-run `xcodegen generate`.
