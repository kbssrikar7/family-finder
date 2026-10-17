# Family location pilot

This is local preparation tooling for evaluating Grid on two Android phones. It is not a new completed family application. On 2026-10-17 the full build passed (analysis, 602 Flutter tests passed with 7 skipped, ARM64 debug APK). The APK is installed on the Galaxy S9+ and launches to onboarding without crashing; Firebase initialization fails gracefully as expected. The loopback Synapse server started and answers on `127.0.0.1:8008`. A Galaxy A23 (Android 14) was then added as the second phone: both phones signed in to dedicated test accounts, paired, and showed each other's live location on the map in both directions over USB forwarding. Background, battery, reboot, revocation and the Nothing phone remain untested.

The source acquisition target is Grid `v2.1.0+1002`, commit `4ecc022817f74db77eadff9cbbd635bafac067e3`. Source remains a separate local checkout; this workspace does not contain a published fork. Grid remains AGPL-3.0; retain its notices and satisfy its license when distributing a derivative. Samsung APKs and decompiled source are not inputs to the pilot.

## Current environment

On 2026-10-17 source bootstrap completed in the user's terminal. Flutter 3.47.7 runs, and the pinned Grid checkout is prepared. The local build copied API 36, Build Tools 35, platform tools and existing licenses into the workspace, then stopped at the NDK download because the sandbox cannot resolve Google download servers. Docker and ADB daemon access also remain unavailable here. Preparation scripts and Compose structure were checked locally; upstream compilation and phone behavior remain unverified.

## Acquire the source and SDK

Run from the workspace root in a terminal with working internet:

```bash
python3 pilot/pilot.py bootstrap
```

Requires Python 3.12+, Git and Linux x86_64. It fetches the pinned Grid tag and verifies the full commit. If Flutter is absent, it downloads Flutter 3.47.7 from Flutter's official release manifest, verifies SHA-256 and extracts it inside `pilot/.local/`. This is a large download. The resolved SDK version and digest are recorded locally. Subsequent invocations retain the existing SDK; the build checks that its version matches the pilot's selected version.

Bootstrap does not run the downloaded application, Gradle or package installation. Inspect the checkout's applicable `AGENTS.md` files and source before executing build steps. In particular, the web-visible `main` source was reviewed, while the selected release's full source could not be downloaded here. Changes between them must be checked locally.

```bash
python3 pilot/pilot.py doctor
```

This reports actual prerequisites, returns 1 when blocked, and supports `doctor --json`. It does not attempt to modify phone settings. Full command diagnostics, when needed, are in `.local/last-command.log`.

## Isolated Matrix server

```bash
python3 pilot/pilot.py init-server
docker compose --env-file pilot/runtime/compose.env -f pilot/compose.yaml config --quiet
docker compose --env-file pilot/runtime/compose.env -f pilot/compose.yaml up -d
curl --fail http://127.0.0.1:8008/_matrix/client/versions
```

The supplied configuration uses SQLite for a two-device experiment, binds the host port to loopback, disables public registration and federation, and creates private random server secrets. Generated files are ignored by Git. The Synapse image is version-pinned; runtime startup and registry availability have not been verified in this sandbox. This is a computer-local trial, not an internet deployment.

Create two dedicated test accounts, entering passwords in your terminal when prompted:

```bash
docker compose --env-file pilot/runtime/compose.env -f pilot/compose.yaml exec synapse register_new_matrix_user -c /data/homeserver.yaml -u pilot-a --no-admin http://localhost:8008
docker compose --env-file pilot/runtime/compose.env -f pilot/compose.yaml exec synapse register_new_matrix_user -c /data/homeserver.yaml -u pilot-b --no-admin http://localhost:8008
```

Do not connect existing Matrix chat accounts. Grid documents cleanup of unrelated rooms. Start with test locations while the key-sharing behavior described in `analysis/grid-source-evaluation.md` is reviewed.

## Prepare a debug Android application

The build command prepares a workspace-local Android SDK in `.local/android-sdk/`. It copies available API 36, Build Tools 35, platform tools, accepted license files and the matching NDK from the existing SDK. Missing packages, including NDK `28.0.12433566`, are requested through the installed `sdkmanager`. The original SDK is not modified. Set `ANDROID_HOME` if the existing SDK is elsewhere. Downloads require a normal terminal with internet; any new license acceptance must be completed through SDK Manager's normal flow.

The downloaded release's `.github/workflows/ci.yml` supplies `https://map.mygrid.app/v1/protomaps.pmtiles`; that upstream map endpoint has been selected for this pilot. Its availability and map rendering still require runtime verification. It means map requests go to Grid's provider while location messages go to the selected Matrix server. The source has already been prepared; the next command is:

```bash
python3 pilot/pilot.py build
```

If analysis and tests passed and only APK compilation failed, retry that stage with `python3 pilot/pilot.py build --apk-only`. This still checks the SDK and resolves the strict dependency lock, but does not repeat analysis or tests. Run the full command again after Dart code or dependency changes.

For a fresh checkout, the equivalent preparation and build commands are:

```bash
python3 pilot/pilot.py prepare-android --maps-url https://map.mygrid.app/v1/protomaps.pmtiles
git -C pilot/.local/grid diff
python3 pilot/pilot.py build
```

The preparation command validates the expected source layout before writing. It backs up the original Android files, changes the application ID to `app.familyfinder.gridpilot` and label to `Family Pilot (Grid)`, avoids evaluating missing release-keystore paths, omits the Firebase Google Services plugin for the unconfigured pilot, and adds a debug-only network policy allowing HTTP solely to `localhost` and `127.0.0.1`. HTTPS is still required for other endpoints. Runtime behavior without Firebase must be tested; push delivery is not provisioned by these scripts.

The build command applies the reviewed Flutter-compatible lock in `locks/`, runs analysis and upstream tests, and then requests an ARM64 debug APK. It first resolves packages from cache under strict lock enforcement, fetching missing packages if needed. Analyzer errors fail the build; warnings and informational lints are reported without being fatal. It stops at the first failure. It writes package/Gradle/analyzer caches under `.local/`, uses the local Android SDK, and does not install an APK. The result, if successful, is `.local/grid/build/app/outputs/flutter-apk/app-debug.apk`.

The compatible lock changes only `matcher`, `meta`, `test`, `test_api`, `test_core` and `vector_math` from the upstream lock, plus the resolved Dart SDK constraint. All other package blocks, including Git commits, are unchanged. The original lock is preserved, and custom user lock changes are not overwritten. Exact versions and checksums are in `locks/manifest.json`.

The build also applies `patches/notification-matrix4.patch`, fixing two API mismatches in the release's notification handler: typed Matrix events use `Event.fromMatrixEvent`, and decryption uses the SDK's encryption service with a generic-notification fallback when it is unavailable. This patch does not change the room-key sharing policy discussed in the source review.

`patches/android-toolchain.patch` updates Gradle to 8.14.3, AGP to 8.13.2 and Kotlin to 2.3.0. These meet the installed Flutter SDK's enforced minimums and align AGP/Kotlin with the selected MapLibre fork. Both Android plugin declaration locations are updated. Gradle uses the smaller binary distribution with its official SHA-256 checksum. Compatibility references: [AGP 8.13.2](https://developer.android.com/build/releases/agp-8-13-0-release-notes), [Gradle checksums](https://gradle.org/release-checksums/). The APK builds with these versions.

`patches/font-icon-compat.patch` fixes a Dart compilation failure in the older Font Awesome package, whose icon classes extend Flutter's now-final `IconData`. The app's only usage is the Discord settings icon. It now uses standard `IconData` pointing to the same code point in the same bundled Font Awesome Brands font. The package remains locked for its font assets, but its incompatible Dart library is no longer imported. An Android ARM64 debug Dart bundle compiled successfully after this change, and the compiled kernel and font assets were verified. The APK now packages successfully.

`patches/plugin-compile-sdk.patch` extends the root Gradle subproject hook so any Android plugin module compiling against an API level below the app's `compileSdkVersion` (36) is raised to it. `flutter_native_splash` 2.4.4 declares API 31, which failed `checkDebugAarMetadata` because its AndroidX dependencies require API 34 or later. Only the compile API level changes; `minSdk` and `targetSdk` are untouched.

`patches/contact-membership.patch` fixes an upstream bug found in the two-phone trial: after the invited contact accepts, the inviter kept showing "Invite pending" and "Sharing with 0" even though locations were exchanged. The timeline join handler sent the location but never persisted the `join` membership, and the contact list prefers the stored status. The patch persists the join and refreshes contacts there, and the contact list now treats a Matrix `join` as authoritative over a stale stored invite, correcting existing records. Two ContactsBloc tests cover the correction and the unsynced-invite case.

`patches/ui-polish.patch` fixes UI issues seen in the trial: the "Sending friend request" notice now clears when the request completes, the friend-request sheet keeps hyphenated handles intact ("Pilot-b", not "Pilot"), the People/Groups/Invites badges update live, and the map opens on the last known position instead of a default location while a fresh fix (about 30 s indoors) is pending.

`patches/resume-tracking.patch` makes sharing survive reboots and app updates. Grid asked for restart-on-boot, but the setting never reached libre_location, so the plugin's saved config had `startOnBoot: false`; the full config is now passed before tracking starts. A package-replaced receiver reuses the plugin's boot path after updates. An application class initializes Flutter before the plugin's background engine starts, which previously crashed the app ("keeps stopping") when tracking restarted without the app open.

`patches/find-device.patch` adds **Play sound**, modeled on Samsung Find's push-delivered device operations (`/devices/{id}/operation/{type}` plus SMP push) and on the open-source FMD app. A contact's profile has a Play sound / Stop sound button. The command is an end-to-end encrypted `m.device.ring` message in the contacts' direct room; it is acted on only if the sender and receiver are both joined to a Grid direct room (checked against the server) and it is under 2 minutes old. The receiving phone plays its alarm tone on the alarm stream at maximum alarm volume (audible in silent/vibrate mode), vibrates, shows a "Found it" notification, restores the previous alarm volume when stopped, and stops after 2 minutes. The open app also answers `m.location.request` while closed.

Push delivery is real UnifiedPush rather than a polling loop: `compose.yaml` runs a pinned ntfy server sharing Synapse's network namespace (Synapse allows pushes to `127.0.0.1` via `ip_range_whitelist`), each phone runs the ntfy app as distributor, and the app registers a Matrix pusher (`event_id_only`). A native `PushService` hands each push to one dedicated headless Flutter engine, which fetches and decrypts the event. Grid's previous UnifiedPush path was a stub, and pushers were only registered for hosted logins.

Device setup per phone: install ntfy from F-Droid (the pilot used 1.25.2, versionCode 63, SHA-256 `b4baa6f668bd57ad5df3b4e0e769165dcf25c5ee19fdb04f78077ee819616f2a`, verified against F-Droid's index), set ntfy's Default server to `http://127.0.0.1:8090`, and `adb reverse tcp:8090 tcp:8090` in addition to 8008. Then open the pilot app once to register.

Measured on the two phones with the receiving app in the background: ring started 1.2 s (S9+ → A23) and 0.7 s (A23 → S9+) after tapping Play sound; remote stop took 0.7-0.8 s; "Found it" stops it locally; alarm audio confirmed on `USAGE_ALARM`; alarm volume restored afterwards. A concurrency bug (two pushes initializing the background Matrix client at once) was found and fixed. Ring status is reported back like Samsung Find's ring state: the ringing phone sends `m.device.ring.status` (`ringing`, then `found` or `timeout`); the finder's button shows "Ringing" once confirmed and resets with a "found their phone" notice. Tapping anywhere on the ringing notification stops it, because Samsung collapses it below other notifications and hides the action button. Verified on both phones.

Encryption hazard found and fixed: when the app's main engine and the background push engine both sent from one device, the receiver failed with "Could not decrypt due to a corrupted session". Pushes are now routed into the main engine's own Matrix client and `MessageProcessor` whenever it is alive; the separate push engine handles them only when the app has no main engine. Grid's existing background location sender (libre_location headless engine) still runs a second client and has the same hazard; it needs the same treatment.

**Find screen** (contact profile → Find), built on existing open-source packages rather than from scratch: `flutter_compass` 0.8.1 (already in Grid's lock) for heading and `ble_proximity_signal` 0.2.1 (BSD-3-Clause) for Bluetooth proximity. It shows an arrow and distance from GPS + compass, switching to "Very close" under 20 m, a Bluetooth warmer/colder meter, and Play sound. While open it sends `live` location requests every 10 s (they bypass Grid's 30-minute response cooldown and ask the other phone for a precise GPS fix) and asks the other phone to broadcast a one-time Bluetooth token for up to 5 minutes (`m.device.nearby`).

Verified: with the phones side by side the meter showed "Very near - within a few metres"; closing the screen stopped the other phone's broadcast. Fixed during testing: the plugin's default 128-bit service UUID made the advertisement 47 bytes (over the 31-byte limit) and failed silently, so a 16-bit-form UUID is used and broadcast errors are logged; Android 11 and older also needed the legacy `BLUETOOTH`/`BLUETOOTH_ADMIN` permissions (added, `maxSdkVersion` 30); minSdk is now 26 (Android 8.0) as the plugin requires.

Not verified: arrow accuracy and live updates outdoors. Indoors the A23 never got a GPS fix (the location plugin fell back to a stale 2 km estimate, which the 100 m send filter correctly drops), so the screen showed an old position. "Very close" can also come from a stale position; the "Updated N min ago" line shows its age. Bluetooth must be on at both ends and "Nearby devices" granted in advance on the lost phone.

`pilot.py` now records applied patches by SHA-256 in `.local/applied-patches.json`: patches are an ordered stack, and a later patch may edit lines an earlier one added, so an earlier patch no longer reverse-applies on a fully patched tree.

Not yet done: Do Not Disturb handling and lost mode.

### Device results (2026-10-17, Galaxy S9+ Android 10, Galaxy A23 Android 14, USB forwarding)

- Two-way sharing: both phones show each other live after pairing, including after remove and re-invite.
- Pause: with sharing paused, restarting the app sent nothing to the paused contact (checked on server and peer).
- Remove contact: the removed person disappears from both phones' lists and maps.
- App update without opening the app: location service restarts within a second.
- Reboot: after the first unlock, Samsung delivered the boot broadcast (delayed while the phone was busy) and sharing resumed without opening the app; the peer received a location 17 s later.
- Screen off 20 min, simulated unplugged: both phones kept sending (server received 14 updates, about every 5 min while stationary); no crashes. App battery use on the S9+ was estimated at 0.7 mAh (1.7 mAh including shared system cost) for the 20 minutes. The A23 did not report a per-app estimate.
- Incoming updates are processed when the app is opened; whether all queued updates display then is not yet confirmed.
- Not tested: Nothing Phone, mobile-data handover, overnight runs, encryption key revocation.

## Two-device USB trial

With an APK built and both phones connected, use the serials from `adb devices -l`:

```bash
adb -s SERIAL_A reverse tcp:8008 tcp:8008
adb -s SERIAL_B reverse tcp:8008 tcp:8008
adb -s SERIAL_A install pilot/.local/grid/build/app/outputs/flutter-apk/app-debug.apk
adb -s SERIAL_B install pilot/.local/grid/build/app/outputs/flutter-apk/app-debug.apk
```

Open the pilot on each phone, select Custom Provider/Custom Server, use `http://127.0.0.1:8008`, and log in with separate test accounts. Grant location permissions through the app's normal screens. Pair using Grid's contact/invitation flow and deliberately enable sharing. Confirm each phone both publishes and receives.

USB forwarding is only a local login/map/sharing experiment. It stops working when disconnected and does not provide location sharing while travelling. Before overnight background, reboot and mobile-network trials, provide an authenticated HTTPS server reachable from both phones; that deployment remains a separate step. Do not interpret a USB-only result as production reliability.

For each trial record: device and OS, app revision, sender fix timestamp and accuracy, receiver update delay, visible stale-state behavior, sharing pause/revocation result, and battery change. Test both directions. Then test revoked access, offline recovery, screen-off operation, reboot and network transitions using the reachable server.

## Check the preparation tools

```bash
python3 -m unittest discover -s pilot -p 'test_*.py' -v
```

These checks validate isolation, configuration preservation and transformation failure behavior. They do not validate encryption, GPS, notifications, battery consumption or Android builds.
