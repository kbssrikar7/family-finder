# Open-source family location sharing research

Research date: 2026-10-17. Reviewed public repositories, declared licenses, documentation and release pages. No candidate was built, installed, security-audited or tested on the family's phones. Feature statements below are project documentation claims; recommendations are our assessment.

## Decision

An independent open-source family location application is feasible. All participating family members would install a compatible client, including the Samsung users. This would support the father's Nothing phone publishing its location and viewing relatives without requiring Samsung device enrollment.

Joining the existing Samsung Find People group is a separate, unresolved interoperability task. Our local Samsung analysis identified account-service and device-enrollment dependencies. The public Samsung projects below do not establish a working replacement for those dependencies on the Nothing phone.

Recommendation: evaluate Grid first for a consumer app and possible contribution/fork; evaluate OwnTracks with Dawarich for a self-hosted family service with history. Start a new implementation only if practical testing identifies requirements these projects cannot satisfy.

## Main candidates

| Project | Documented capability | Declared license / scope | Assessment |
| --- | --- | --- | --- |
| [Grid](https://github.com/Rezivure/Grid-Mobile) | Flutter Android/iOS; live individual/group sharing, revocation, Matrix encryption; self-hostable server and maps | AGPL-3.0 mobile application | Closest app-shaped starting point for our goal |
| [OwnTracks](https://github.com/owntracks/android) | Publishes location and displays other permitted users; Android variants with and without Google services | Android client EPL-1.0; related components have their own licenses | Practical basic family sharing, with more configuration |
| [Dawarich](https://github.com/Freika/dawarich) | Self-hosted maps, timelines and family location/history sharing | AGPL-3.0 server | Strong choice when family history and a web dashboard matter |
| [Traccar](https://github.com/traccar/traccar) | Server tracking, phone reporting clients and viewing/management clients | Apache-2.0 server; verify selected client components separately | Useful infrastructure; more tracking administration than family onboarding |
| [Paralino](https://github.com/paralino/paralino) | Android/iOS clients; project advertises encrypted groups, history, geofences and alerts | AGPL-3.0 mobile source | Worth comparing for UX; public self-hostable backend was not established by this review |

### Grid

The project documents a Synapse backend and a small team with one developer. Use a dedicated Matrix account: Grid can remove non-Grid rooms. Federation is not tested, and map requests have a separate privacy model from encrypted location messages. Those constraints matter when choosing an isolated pilot configuration. [Architecture and limitations](https://docs.mygrid.app/docs/intro/), [self-hosting guides](https://docs.mygrid.app/docs/category/self-hosting/).

The release page includes Android APKs and fixes to location accuracy and sharing behavior. Release availability is evidence of development, not proof of reliable background operation on these phones. [Releases](https://github.com/Rezivure/Grid-Mobile/releases).

### OwnTracks and Dawarich

OwnTracks explicitly documents bidirectional Friends and Family sharing through a shared MQTT broker with permission-controlled subscriptions. This covers both publishing and viewing; it is not just a location uploader. [Friends documentation](https://owntracks.org/booklet/features/friends/).

Dawarich documents separate controls for live location and recent history, invitations, and family functionality without a member limit on self-hosted installations. It also documents returning relatives' current positions to OwnTracks HTTP clients. This is an alternative to OwnTracks' MQTT arrangement, not a requirement to deploy both transports. [Family documentation](https://dawarich.app/docs/features/family/).

OwnTracks offers a setup helper, while Dawarich adds a larger web application to operate. Review current release/security notes when pinning an OwnTracks build; this research does not certify a particular stable or beta package. [Quicksetup](https://github.com/owntracks/quicksetup), [Android releases](https://github.com/owntracks/android/releases).

### Traccar

The reporting app and management/viewing app are distinct products. [Client](https://www.traccar.org/client/), [Manager](https://www.traccar.org/manager/).

For a new application, the Apache-2.0 [Traccar Client SDK](https://github.com/traccar/traccar-client-sdk) is a component to evaluate: background location on Android/iOS with Flutter and React Native wrappers. It does not provide a complete family application, account system or end-to-end encryption. Build compatibility and a suitable release must be checked before selecting it.

## Samsung interoperability projects

| Project | What the public project establishes | What remains unproven for us |
| --- | --- | --- |
| [uTag](https://github.com/KieronQuinn/uTag) | SmartTags on non-Samsung Android 11+, through modified SmartThings; GPL-3.0 project | Making the Nothing phone a Samsung Find People sharing device |
| [samsung-re-find](https://github.com/charlesbel/samsung-re-find) | Unofficial MIT Python SDK/CLI/MCP for existing Samsung devices, available locations and supported commands | New non-Samsung phone enrollment and a complete two-way family app |
| [HA-SmartThings-Find](https://github.com/coldfire88/HA-SmartThings-Find) | Unofficial MIT Home Assistant integration for supported Samsung device locations and actions | Coverage of the family's People shares or publishing the Nothing phone into Samsung Find |

uTag's build also relies on a Samsung library and modified SmartThings, so it is not a Samsung-independent replacement stack. Private Samsung API access remains dependent on Samsung services. A documented device-location read capability must not be treated as proof of People-sharing enrollment.

A possible hybrid is a Home Assistant dashboard receiving the father's location from [Home Assistant Companion](https://companion.home-assistant.io/docs/core/location/) and supported Samsung device locations from an unofficial integration. This is a proposed architecture, not a tested combination. It would not itself add the Nothing phone to Samsung Find, and access to every relative's shared location is unverified.

## Other projects considered

- [Hauk](https://github.com/bilde2910/Hauk): Apache-2.0, self-hosted Android location sharing with a browser viewer. Worth considering for a smaller sharing service; not our first choice for a complete family application.
- [Find-Family](https://github.com/vayun-mathur/Find-Family): the original repository is archived and directs Android development to [Modern-Apps/findfamily](https://github.com/vayun-mathur/Modern-Apps/tree/main/findfamily). Avoid selecting the archived repository without examining the successor and backend requirements.
- Paralino publishes mobile source, but this review did not locate sufficient evidence to recommend it as a fully self-hostable stack. Its [website](https://paralino.com/) offers a hosted service; source availability and a complete independent deployment are different questions.

## If we build

Implement a new product using appropriately licensed open-source components, keeping proprietary Samsung decompiled code and APKs out of its public source.

First version: explicit family invitations and acceptance, two-way map sharing, background location, timestamps and accuracy, sharing pause/revocation, offline upload recovery, and deletion/retention controls. If encryption is a requirement, establish the key and device-management design from the start.

The first engineering milestone should be a background-operation trial on the actual S9+ and Nothing Phone (3a): screen off, overnight idle, network changes, reboot and battery restrictions. A stale position must remain visibly stale. This trial should determine whether adapting an existing client is sufficient.

Keep Samsung interoperability optional until enrollment and People access are demonstrated. Replacing family sharing does not reproduce Samsung's crowd-powered offline finding network, privileged remote-control functions or SmartTag ecosystem.
