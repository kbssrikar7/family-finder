<div align="center">

# Family Finder

A private "Find My" for mixed families: live location sharing, ring a lost phone, and find it
nearby, across Samsung, Nothing and other Android phones, on a server you control.

![Platform](https://img.shields.io/badge/platform-Android%208.0%2B-green)
![Status](https://img.shields.io/badge/status-pilot-orange)
![License](https://img.shields.io/badge/license-AGPL--3.0-blue)

</div>

---

## Why this exists

Apple's Find My, Samsung Find and Google Find Hub each work well, but only within their own
ecosystem. A family with a Samsung, a Nothing phone and an iPhone has no single app where everyone
can see each other and ring each other's phones.

Family Finder is built on [Grid](https://github.com/Rezivure/Grid-Mobile), an open-source,
end-to-end encrypted location-sharing app on the Matrix protocol. This repository holds a
reproducible build of Grid plus the find-my-phone features below, delivered as tooling and patches
rather than a copy of Grid's source.

## Features

| Feature | Status |
|---|---|
| Live two-way location sharing, end-to-end encrypted | Working, tested on Galaxy S9+, A23 and S21 |
| Pause sharing, remove a contact | Working |
| **Play sound**: ring a contact's phone at full alarm volume, even on silent | Working, about 1 s over push with the app in the background |
| Ring feedback: "Ringing", "Found their phone", "Stopped ringing" | Working |
| **Find screen**: arrow and distance, live location every 10 s while open | Built; arrow accuracy not yet tested outdoors |
| **Nearby**: Bluetooth warmer/colder meter for the last few metres | Working |
| Survives reboots, app updates and screen-off | Working |
| Lost mode | Planned |
| iPhone build | Planned (needs a Mac and Apple developer account) |
| Internet-reachable server | Planned; the pilot runs over USB forwarding |

The ring and nearby designs follow Samsung Find's push-delivered device operations and the
open-source [FMD](https://gitlab.com/fmd-foss/fmd-android) app. Commands travel as encrypted Matrix
messages between contacts, woken by a self-hosted [ntfy](https://ntfy.sh) UnifiedPush server. Only a
mutual contact can ring your phone, and stale commands are ignored.

## Quick start

Requirements: Linux x86_64, Python 3.12+, Git, Docker, and `adb` for installing on phones.

```bash
python3 pilot/pilot.py doctor          # check prerequisites
python3 pilot/pilot.py bootstrap       # fetch pinned Grid source and Flutter SDK
python3 pilot/pilot.py prepare-android --maps-url https://map.mygrid.app/v1/protomaps.pmtiles
python3 pilot/pilot.py init-server     # private Synapse + ntfy configuration
docker compose --env-file pilot/runtime/compose.env -f pilot/compose.yaml up -d
python3 pilot/pilot.py build           # patches, analysis, tests, ARM64 debug APK
```

The APK lands at `pilot/.local/grid/build/app/outputs/flutter-apk/app-debug.apk`. Phone setup
(test accounts, ntfy, port forwarding) and every verified result are in
[`pilot/README.md`](pilot/README.md).

## How it is built

- `pilot/pilot.py` downloads Grid at a pinned commit, applies the patches in order, resolves a
  reviewed dependency lock, then runs analysis, all Flutter tests and the APK build.
- `pilot/patches/` holds every change to Grid, one concern per patch, applied as an ordered stack.
- `pilot/locks/` holds the dependency lock and a manifest of every package change.
- `pilot/compose.yaml` runs a loopback-only Synapse homeserver and ntfy push server.

## Contributing

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[AGPL-3.0](LICENSE), the same as Grid. The patches modify Grid, so any distributed build must offer
its source under the same license. Bundled dependencies keep their own licenses.

## Disclaimer

This is an independent project, not affiliated with Grid, Samsung, Google, Apple or Nothing. It is
a pilot: test with dedicated accounts before sharing real family locations.
