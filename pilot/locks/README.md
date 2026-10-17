# Flutter compatibility lock

This lock is derived from Grid commit `4ecc022817f74db77eadff9cbbd635bafac067e3` and resolved locally using Flutter 3.47.7 / Dart 3.13.5 on 2026-10-17. The unmodified Grid lock could not satisfy that SDK's pinned dependencies.

Only six package blocks and the resolved Dart SDK constraint differ. `manifest.json` records the versions and both file digests. Strict offline dependency resolution succeeds with the supplied lock. This establishes a resolvable package graph, not a completed Android build or phone compatibility result.

The source checkout retains Grid's AGPL-3.0 license. Dependency licenses remain those of their respective packages.

Find-device additions (2026-10-17): `ble_proximity_signal` 0.2.1 and its three platform packages (BSD-3-Clause) were added, and `flutter_compass` 0.8.1 became a direct dependency at its already-locked version. Resolution added only these packages; no existing package version changed. `manifest.json` lists them.
