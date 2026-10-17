# Grid pilot: source evaluation and limits

Date: 2026-10-17. This is a targeted browser inspection, not a full source or security audit. Browser results exposed `main` snapshots with different crawl dates. The selected release's full source was not retrievable, so release-specific changes must be checked after bootstrap.

Update after bootstrap: the selected release is now downloaded and its exact commit verified locally. The inspected Android build configuration, direct custom-server login, and permissive key-forwarding handler are also present in that release. Android pilot transformations have been applied successfully. Flutter 3.47.7 executes. A build attempt stopped during NDK acquisition because this sandbox cannot resolve Google download servers; dependencies, analysis, app tests and compilation have not completed. A workspace-local SDK preserves the user's original SDK.

Latest build update: the user installed the NDK. Strict resolution of the original lock failed because the selected Flutter SDK pins six different dependency versions. The reviewed compatibility lock now resolves successfully offline under strict enforcement; see `pilot/locks/manifest.json`. This follows the documented distinction between ordinary resolution and [lock enforcement](https://dart.dev/tools/pub/cmd/pub-get).

Local analysis exposed two existing Matrix 4 API mismatches in encrypted-notification handling. The saved pilot patch uses the SDK's typed event factory and encryption service. Analysis then completed with zero errors (existing warnings and informational lints remain). All 13 preparation tests pass. The full Flutter test attempt could not load any test files because the sandbox denies binding the test runner's loopback socket; this is an environmental failure, not a passing app test result. Android compilation still requires the normal terminal for network/socket access.

## Useful evidence

- [Custom-server login](https://github.com/Rezivure/Grid-Mobile/blob/main/lib/screens/onboarding/login_screen.dart) calls Matrix homeserver discovery and password login directly and accepts an explicit HTTP URL. This supports a loopback USB pilot without assuming the hosted authentication service can be reimplemented trivially.
- [Environment template](https://github.com/Rezivure/Grid-Mobile/blob/main/.env.example) leaves endpoint values blank. A fork therefore needs deliberate configuration; no working map URL was established by this inspection.
- [Android app build](https://github.com/Rezivure/Grid-Mobile/blob/main/android/app/build.gradle) applies Google Services, expects release-signing properties, and selects NDK 28.0.12433566 and Java 21. Pilot preparation handles known Gradle configuration obstacles without claiming Firebase-free runtime success.
- [Root Android build](https://github.com/Rezivure/Grid-Mobile/blob/main/android/build.gradle) specifies API 36 and minimum API 24. Those declared OS requirements fit the expected phone generations, but do not prove device compatibility.
- [Package manifest](https://github.com/Rezivure/Grid-Mobile/blob/main/pubspec.yaml) includes Matrix/native encryption, location and push dependencies, plus Git-based overrides. Locked transitive dependencies and native builds must be verified after acquisition.

## Privacy behavior requiring review

The inspected [main entry point](https://github.com/Rezivure/Grid-Mobile/blob/main/lib/main.dart) configures key sharing across devices. Its room-key request handler explicitly rejects leave/ban membership, but also forwards keys on unknown membership or membership-query failure. This is a concrete behavior to review against Matrix SDK server-side authorization and revoked-access semantics. The inspection does not establish an exploitable vulnerability. Confirm whether the pinned release contains it and test removal/revocation before real family locations are used.

The initial pilot therefore uses dedicated test accounts. No code was changed to invent an unverified cryptographic fix.

## Release and server selection

- [Grid v2.1.0+1002](https://github.com/Rezivure/Grid-Mobile/releases/tag/v2.1.0%2B1002), commit `4ecc022817f74db77eadff9cbbd635bafac067e3`, is the selected source baseline. The fetch command rejects a moved tag.
- [Synapse v1.163.0](https://github.com/element-hq/synapse/releases/tag/v1.163.0) is the selected server version. Its container has not been pulled or started here.
- [Official Synapse configuration](https://element-hq.github.io/synapse/latest/usage/configuration/config_documentation.html) documents disabling federation with an empty federation-domain allowlist. The pilot also omits a federation listener and exposes the client listener only on host loopback.
- [Grid self-hosting documentation](https://docs.mygrid.app/docs/self-hosting/creating-a-server/) describes custom-provider login; its dedicated-account requirement is retained.

## What was actually completed

Prepared pinned acquisition tooling, private server configuration, separate Android debug-variant preparation, prerequisite reporting and local preparation tests. Compose structure is independently checkable without Docker daemon access.

Not completed: source clone, Flutter acquisition, Android patch application, dependency resolution, compilation, upstream tests, live Synapse startup, phone installation, encryption assessment or two-way location testing. Network DNS and daemon/socket access block those steps in this sandbox; Flutter and the required NDK are also absent.
