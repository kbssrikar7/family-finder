#!/usr/bin/env python3
"""Prepare an isolated Grid evaluation; Python 3.12+, standard library only."""
import sys

VERSION = "0.3.2"
if __name__ == "__main__" and sys.argv[1:] in (["--version"], ["-v"], ["-V"]):
    print(VERSION)
    raise SystemExit(0)

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / ".local"
SOURCE = LOCAL / "grid"
GRID_REPO = "https://github.com/Rezivure/Grid-Mobile.git"
GRID_TAG = "v2.1.0+1002"
GRID_COMMIT = "4ecc022817f74db77eadff9cbbd635bafac067e3"
FLUTTER_BASE = "https://storage.googleapis.com/flutter_infra_release/releases"
FLUTTER_VERSION = "3.47.7"
ANDROID = "http://schemas.android.com/apk/res/android"
NDK_VERSION = "28.0.12433566"


def installed_sdk():
    return Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))


def build_environment():
    env = {**os.environ, "PUB_CACHE": str(LOCAL / "pub-cache"),
           "GRADLE_USER_HOME": str(LOCAL / "gradle"),
           "ANDROID_USER_HOME": str(LOCAL / "android-user"),
           "XDG_CONFIG_HOME": str(LOCAL / "config"),
           "XDG_CACHE_HOME": str(LOCAL / "cache"),
           "ANALYZER_STATE_LOCATION_OVERRIDE": str(LOCAL / "analyzer-cache"),
           "CI": "true", "FLUTTER_SUPPRESS_ANALYTICS": "true"}
    env["PATH"] = str(LOCAL / "flutter/bin") + os.pathsep + env.get("PATH", "")
    return env


class PilotError(Exception):
    pass


def emit(**fields):
    # A flat TOON object; quoted scalars use JSON's escaping rules.
    for key, value in fields.items():
        print(f"{key}: {json.dumps(value, ensure_ascii=False)}")


def run(args, *, cwd=ROOT, env=None, timeout=60):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                            text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    LOCAL.mkdir(parents=True, exist_ok=True)
    log = LOCAL / "last-command.log"
    log.write_text(result.stdout + result.stderr)
    log.chmod(0o600)
    if result.returncode:
        # Keep full build diagnostics in a private log, not structured stdout.
        raise PilotError(f"Command failed ({Path(args[0]).name}); diagnostics: {log}")
    return result.stdout.strip()


def private_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        stream.write(content)


def open_download(url, *, timeout):
    try:
        return urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.HTTPError as error:
        raise PilotError(f"Download failed (HTTP {error.code}): {url}") from error


def doctor(as_json=False):
    sdk = LOCAL / "android-sdk" if (LOCAL / "android-sdk").is_dir() else installed_sdk()
    checks = {
        "grid_source": "ready" if (SOURCE / "pubspec.yaml").is_file() else "missing",
        "flutter": "ready" if (LOCAL / "flutter/bin/flutter").is_file() or shutil.which("flutter") else "missing",
        "java": "ready" if shutil.which("java") else "missing",
        "android_sdk": "ready" if (sdk / "platforms/android-36").is_dir() else "missing API 36",
        "android_ndk": "ready" if (sdk / "ndk/28.0.12433566").is_dir() else "missing NDK 28.0.12433566",
        "server_config": "ready" if (ROOT / "runtime/data/homeserver.yaml").is_file() else "missing",
    }
    try:
        socket.getaddrinfo("github.com", 443)
        checks["github_dns"] = "ready"
    except OSError:
        checks["github_dns"] = "unavailable"
    try:
        run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=10)
        checks["docker_daemon"] = "ready"
    except (OSError, PilotError, subprocess.TimeoutExpired):
        checks["docker_daemon"] = "unavailable"
    payload = {"status": "ready" if all(v == "ready" for v in checks.values()) else "blocked", **checks}
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        emit(bin=str(Path(__file__).resolve()), description=__doc__, **payload,
             help="python3 pilot/pilot.py bootstrap; python3 pilot/pilot.py init-server")
    return 0 if payload["status"] == "ready" else 1


def bootstrap():
    """Download only: do not execute upstream build scripts or change phones."""
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise PilotError("Automatic SDK preparation supports Linux x86_64; install Flutter manually on this host.")
    LOCAL.mkdir(parents=True, exist_ok=True)
    if SOURCE.exists():
        commit = run(["git", "rev-parse", "HEAD"], cwd=SOURCE)
        if commit != GRID_COMMIT:
            raise PilotError("Existing source is a different revision; preserve it and review before changing it.")
    else:
        print("Downloading pinned Grid source...", file=sys.stderr)
        with tempfile.TemporaryDirectory(dir=LOCAL) as temporary:
            target = Path(temporary) / "grid"
            env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            run(["git", "clone", "--depth", "1", "--branch", GRID_TAG,
                 GRID_REPO, str(target)], env=env, timeout=180)
            if run(["git", "rev-parse", "HEAD"], cwd=target) != GRID_COMMIT:
                raise PilotError("Upstream tag no longer matches the selected commit; no source was installed.")
            target.rename(SOURCE)
    provenance = LOCAL / "source.json"
    provenance.write_text(json.dumps({"repository": GRID_REPO, "tag": GRID_TAG,
                                     "commit": GRID_COMMIT}, indent=2) + "\n")
    if not (LOCAL / "flutter/bin/flutter").is_file() and not shutil.which("flutter"):
        print("Downloading official stable Flutter SDK (large download)...", file=sys.stderr)
        with open_download(FLUTTER_BASE + "/releases_linux.json", timeout=30) as response:
            manifest = json.load(response)
        release = next(item for item in manifest["releases"]
                       if item.get("version") == FLUTTER_VERSION and item.get("channel") == "stable"
                       and item.get("dart_sdk_arch", "x64") == "x64")
        archive_path = release["archive"]
        if not re.fullmatch(r"stable/linux/[A-Za-z0-9_.-]+\.tar\.xz", archive_path):
            raise PilotError("Unexpected Flutter archive path in official manifest.")
        with tempfile.TemporaryDirectory(dir=LOCAL) as temporary:
            archive = Path(temporary) / "flutter.tar.xz"
            digest = hashlib.sha256()
            with open_download(FLUTTER_BASE + "/" + archive_path, timeout=60) as response, archive.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    stream.write(chunk)
            if digest.hexdigest() != release["sha256"]:
                raise PilotError("Flutter archive checksum mismatch; nothing extracted.")
            unpacked = Path(temporary) / "unpacked"
            unpacked.mkdir()
            with tarfile.open(archive) as package:
                package.extractall(unpacked, filter="data")
            (unpacked / "flutter").rename(LOCAL / "flutter")
        (LOCAL / "flutter-release.json").write_text(json.dumps(release, indent=2) + "\n")
    emit(status="prepared", source=str(SOURCE), commit=GRID_COMMIT,
         help="Review upstream AGENTS.md files and source before running prepare-android or build.")


def init_server():
    data = ROOT / "runtime/data"
    config_path = data / "homeserver.yaml"
    if config_path.exists():
        emit(status="unchanged", config=str(config_path))
        return
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    (ROOT / "runtime/ntfy").mkdir(parents=True, exist_ok=True, mode=0o700)
    log_config = {
        "version": 1,
        "formatters": {"brief": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "brief"}},
        "root": {"level": "INFO", "handlers": ["console"]},
        "disable_existing_loggers": False,
    }
    config = {
        "server_name": "localhost",
        "public_baseurl": "http://127.0.0.1:8008/",
        "pid_file": "/data/homeserver.pid",
        "listeners": [{"port": 8008, "tls": False, "type": "http",
                       "bind_addresses": ["0.0.0.0"], "x_forwarded": False,
                       "resources": [{"names": ["client"], "compress": False}]}],
        "database": {"name": "sqlite3", "args": {"database": "/data/homeserver.db"}},
        "log_config": "/data/log.config",
        "media_store_path": "/data/media_store",
        "signing_key_path": "/data/localhost.signing.key",
        "report_stats": False,
        "enable_registration": False,
        "registration_shared_secret": secrets.token_hex(32),
        "macaroon_secret_key": secrets.token_hex(32),
        "form_secret": secrets.token_hex(32),
        "federation_domain_whitelist": [],
        "trusted_key_servers": [],
        "suppress_key_server_warning": True,
        # Pushes go to the ntfy gateway sharing Synapse's loopback (compose.yaml);
        # Synapse blocks outbound requests to private addresses by default.
        "ip_range_whitelist": ["127.0.0.1/32"],
    }
    # JSON is valid YAML; avoid a Python YAML dependency for local preparation.
    private_write(config_path, json.dumps(config, indent=2) + "\n")
    log_path = data / "log.config"
    if not log_path.exists():
        private_write(log_path, json.dumps(log_config, indent=2) + "\n")
    env_path = ROOT / "runtime/compose.env"
    if not env_path.exists():
        private_write(env_path, f"PILOT_UID={os.getuid()}\nPILOT_GID={os.getgid()}\n")
    emit(status="prepared", config=str(config_path),
         help="docker compose --env-file pilot/runtime/compose.env -f pilot/compose.yaml up -d")


def prepare_android(maps_url):
    parsed = urllib.parse.urlsplit(maps_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.fragment or any(c in maps_url for c in "\r\n\"' ")):
        raise PilotError("--maps-url must be an HTTPS PMTiles URL without whitespace or quotes.")
    if not (SOURCE / "pubspec.yaml").is_file():
        raise PilotError("Source missing; run python3 pilot/pilot.py bootstrap first.")
    if run(["git", "rev-parse", "HEAD"], cwd=SOURCE) != GRID_COMMIT:
        raise PilotError("Source revision differs from the pinned pilot revision.")
    stamp = LOCAL / "android-prepared.json"
    if stamp.exists():
        if json.loads(stamp.read_text())["maps_url"] != maps_url:
            raise PilotError("Pilot already prepared with another map source; review .env before changing it.")
        emit(status="unchanged", source=str(SOURCE))
        return
    gradle = SOURCE / "android/app/build.gradle"
    original = gradle.read_text()
    replacements = {
        'id "com.google.gms.google-services"': '// Pilot: Firebase credentials are not configured.',
        'applicationId "app.mygrid.grid"': 'applicationId "app.familyfinder.gridpilot"',
        "storeFile file(localProperties.getProperty('storeFile'))":
            "storeFile localProperties.getProperty('storeFile') ? file(localProperties.getProperty('storeFile')) : null",
    }
    updated = original
    for before, after in replacements.items():
        if updated.count(before) != 1:
            raise PilotError("Upstream Android build layout differs; review before applying the pilot changes.")
        updated = updated.replace(before, after, 1)
    manifest = SOURCE / "android/app/src/main/AndroidManifest.xml"
    original_manifest = manifest.read_text()
    if original_manifest.count('android:label="Grid"') != 1:
        raise PilotError("Unexpected Android app label; review the manifest before adapting it.")
    debug = SOURCE / "android/app/src/debug/AndroidManifest.xml"
    ET.register_namespace("android", ANDROID)
    tree = ET.fromstring(debug.read_text()) if debug.exists() else ET.Element("manifest")
    application = tree.find("application")
    if application is None:
        application = ET.SubElement(tree, "application")
    if f"{{{ANDROID}}}networkSecurityConfig" in application.attrib:
        raise PilotError("Existing debug network policy requires manual review.")
    application.attrib.pop(f"{{{ANDROID}}}usesCleartextTraffic", None)
    application.set(f"{{{ANDROID}}}networkSecurityConfig", "@xml/pilot_network_security_config")
    env_path = SOURCE / ".env"
    if env_path.exists():
        raise PilotError("Existing Grid .env preserved; review it before preparing the pilot.")
    environment = (SOURCE / ".env.example").read_text()
    if len(re.findall(r"(?m)^MAPS_URL=$", environment)) != 1:
        raise PilotError("Unexpected .env template; no configuration changed.")
    environment = re.sub(r"(?m)^MAPS_URL=$", lambda match: f"MAPS_URL={maps_url}", environment)
    # Validate every input before writing any upstream files.
    backup = LOCAL / "android-originals"
    for path in (gradle, manifest, debug):
        if path.exists():
            destination = backup / path.relative_to(SOURCE)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(path.read_bytes())
    gradle.write_text(updated)
    manifest.write_text(original_manifest.replace('android:label="Grid"', 'android:label="Family Pilot (Grid)"'))
    debug.parent.mkdir(parents=True, exist_ok=True)
    debug.write_text("\n".join(line.rstrip() for line in ET.tostring(tree, encoding="unicode").splitlines()) + "\n")
    policy = SOURCE / "android/app/src/debug/res/xml/pilot_network_security_config.xml"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text('<network-security-config>\n  <base-config cleartextTrafficPermitted="false"/>\n'
                      '  <domain-config cleartextTrafficPermitted="true">\n'
                      '    <domain>127.0.0.1</domain><domain>localhost</domain>\n'
                      '  </domain-config>\n</network-security-config>\n')
    private_write(env_path, environment)
    stamp.write_text(json.dumps({"commit": GRID_COMMIT, "maps_url": maps_url,
                                "application_id": "app.familyfinder.gridpilot"}, indent=2) + "\n")
    emit(status="prepared", application_id="app.familyfinder.gridpilot",
         help="Review git diff in pilot/.local/grid, then run python3 pilot/pilot.py build.")


def build(apk_only=False):
    if not (LOCAL / "android-prepared.json").exists():
        raise PilotError("Run prepare-android --maps-url <https-pmtiles-url> before building.")
    flutter = LOCAL / "flutter/bin/flutter"
    executable = str(flutter) if flutter.is_file() else shutil.which("flutter")
    if not executable:
        raise PilotError("Flutter missing; run python3 pilot/pilot.py bootstrap.")
    env = build_environment()
    sdk_info = json.loads(run([executable, "--version", "--machine"], env=env))
    if sdk_info.get("frameworkVersion") != FLUTTER_VERSION:
        raise PilotError(f"This pilot requires Flutter {FLUTTER_VERSION}; the selected SDK version differs.")
    apply_source_fixes()
    apply_dependency_lock()
    sdk = setup_android_sdk(env)
    env["ANDROID_HOME"] = str(sdk)
    env["ANDROID_SDK_ROOT"] = str(sdk)
    # Flutter checks this file before invoking Gradle; replace only the SDK path.
    properties = SOURCE / "android/local.properties"
    existing = properties.read_text() if properties.exists() else ""
    lines = [line for line in existing.splitlines() if not line.startswith("sdk.dir=")]
    sdk_property = str(sdk).replace("\\", "\\\\").replace(" ", "\\ ")
    properties.write_text("\n".join([*lines, f"sdk.dir={sdk_property}"]) + "\n")
    print("Resolving locked dependencies from cache...", file=sys.stderr)
    try:
        run([executable, "pub", "get", "--offline", "--enforce-lockfile"], cwd=SOURCE, env=env, timeout=180)
    except PilotError:
        print("Fetching missing locked dependencies...", file=sys.stderr)
        run([executable, "pub", "get", "--enforce-lockfile"], cwd=SOURCE, env=env, timeout=1800)
    checks = [] if apk_only else [
        [executable, "analyze", "--no-pub", "--no-fatal-infos", "--no-fatal-warnings"],
        [executable, "test", "--no-pub"],
    ]
    if apk_only:
        print("APK retry: analysis and tests are not rerun; use after a successful check run.", file=sys.stderr)
    for args in [*checks, [executable, "build", "apk", "--debug", "--no-pub", "--target-platform", "android-arm64"]]:
        print("Running " + " ".join(args[1:]) + "...", file=sys.stderr)
        run(args, cwd=SOURCE, env=env, timeout=1800)
    apk = SOURCE / "build/app/outputs/flutter-apk/app-debug.apk"
    emit(status="built", apk=str(apk), sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
         help="Follow pilot/README.md to connect two test devices; no APK was installed automatically.")


def apply_dependency_lock():
    """Apply the reviewed Flutter compatibility lock; preserve custom changes."""
    directory = ROOT / "locks"
    manifest = json.loads((directory / "manifest.json").read_text())
    candidate = (directory / manifest["lockfile"]).read_bytes()
    if hashlib.sha256(candidate).hexdigest() != manifest["pilot_sha256"]:
        raise PilotError("Pilot dependency lock checksum differs from its manifest; review before building.")
    lock = SOURCE / "pubspec.lock"
    current = lock.read_bytes()
    digest = hashlib.sha256(current).hexdigest()
    if digest == manifest["pilot_sha256"]:
        return
    if digest != manifest["upstream_sha256"]:
        raise PilotError("Existing dependency lock has custom changes; preserved for review.")
    backup = LOCAL / "upstream-pubspec.lock"
    if not backup.exists():
        backup.write_bytes(current)
    lock.write_bytes(candidate)


def apply_source_fixes():
    # Patches are an ordered stack: later ones may edit lines earlier ones
    # added, so "already applied" is recorded rather than inferred.
    record = LOCAL / "applied-patches.json"
    applied = json.loads(record.read_text()) if record.exists() else {}
    for name in ("notification-matrix4.patch", "android-toolchain.patch", "font-icon-compat.patch",
                 "plugin-compile-sdk.patch", "contact-membership.patch",
                 "ui-polish.patch", "resume-tracking.patch",
                 "find-device.patch"):
        patch_path = ROOT / "patches" / name
        patch = str(patch_path)
        digest = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        if applied.get(name) == digest:
            continue  # Recorded as applied; later patches may build on it.
        try:
            # Untracked tree state (e.g. before this record existed).
            run(["git", "apply", "--reverse", "--check", patch], cwd=SOURCE)
        except PilotError:
            run(["git", "apply", "--check", patch], cwd=SOURCE)
            run(["git", "apply", patch], cwd=SOURCE)
        applied[name] = digest
        record.write_text(json.dumps(applied, indent=2) + "\n")


def setup_android_sdk(env):
    """Copy existing SDK packages, then install missing packages in the workspace."""
    sdk = LOCAL / "android-sdk"
    origin = installed_sdk()
    sdk.mkdir(parents=True, exist_ok=True)
    # Copies rather than symlinks: package installation must not write through
    # into the user's existing SDK. Incomplete copies never replace a package.
    packages = ("platforms/android-36", "build-tools/35.0.0", "platform-tools",
                "licenses", f"ndk/{NDK_VERSION}")
    for relative in packages:
        source, destination = origin / relative, sdk / relative
        if source.is_dir() and not destination.exists():
            print(f"Preparing local SDK package: {relative}...", file=sys.stderr)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=LOCAL) as temporary:
                copied = Path(temporary) / "package"
                shutil.copytree(source, copied)
                copied.rename(destination)
    required = {"platforms;android-36": sdk / "platforms/android-36",
                "build-tools;35.0.0": sdk / "build-tools/35.0.0",
                "platform-tools": sdk / "platform-tools",
                f"ndk;{NDK_VERSION}": sdk / f"ndk/{NDK_VERSION}"}
    missing = [name for name, path in required.items() if not path.is_dir()]
    if missing:
        manager = shutil.which("sdkmanager")
        if not manager:
            raise PilotError("Android SDK Manager is missing; install Android command-line tools and retry build.")
        try:
            socket.getaddrinfo("dl.google.com", 443)
        except OSError as error:
            raise PilotError("Android downloads are unavailable here; run python3 pilot/pilot.py build in your normal terminal with internet access.") from error
        print("Installing local Android packages: " + ", ".join(missing) + "...", file=sys.stderr)
        output = run([manager, f"--sdk_root={sdk}", "--channel=3", "--include_obsolete", "--install", *missing],
                     env={**env, "ANDROID_HOME": str(sdk), "ANDROID_SDK_ROOT": str(sdk)}, timeout=1800)
        if "license is not accepted" in output.lower() or "licenses not accepted" in output.lower():
            raise PilotError(
                "Android SDK license acceptance is required. Installation runs without interactive input. "
                f"Run sdkmanager --sdk_root={sdk} --channel=3 --install "
                + " ".join(f'\"{package}\"' for package in missing)
                + " in your terminal to review the license, then rerun python3 pilot/pilot.py build.")
        if any(not path.is_dir() for path in required.values()):
            raise PilotError(f"Android packages remain missing; review {LOCAL / 'last-command.log'}. If a license needs acceptance, use sdkmanager --sdk_root={sdk} --licenses in your terminal.")
    return sdk


class Parser(argparse.ArgumentParser):
    def error(self, message):
        emit(error=message, help=self.format_help().strip())
        raise SystemExit(2)


def main():
    parser = Parser(description=__doc__, allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", parser_class=Parser)
    check = sub.add_parser("doctor", help="Check source, SDK and local server prerequisites.", allow_abbrev=False)
    check.add_argument("--json", action="store_true", help="Output JSON instead of TOON.")
    sub.add_parser("bootstrap", help="Download pinned Grid source and a verified stable Flutter SDK.", allow_abbrev=False)
    sub.add_parser("init-server", help="Generate private loopback-only Matrix server configuration.", allow_abbrev=False)
    prepare = sub.add_parser("prepare-android", help="Adapt the pinned checkout for a separate debug pilot.", allow_abbrev=False)
    prepare.add_argument("--maps-url", required=True, help="HTTPS URL to a compatible PMTiles map archive.")
    build_parser = sub.add_parser("build", help="Resolve locked packages, analyze, test and build a debug ARM64 APK.", allow_abbrev=False)
    build_parser.add_argument("--apk-only", action="store_true", help="Retry APK compilation after analysis and tests already passed.")
    args = parser.parse_args()
    try:
        if args.command in (None, "doctor"):
            return doctor(getattr(args, "json", False))
        if args.command == "bootstrap":
            bootstrap()
        elif args.command == "init-server":
            init_server()
        elif args.command == "prepare-android":
            prepare_android(args.maps_url)
        elif args.command == "build":
            build(apk_only=args.apk_only)
        return 0
    except (PilotError, OSError, ValueError, KeyError, StopIteration, ET.ParseError,
            tarfile.TarError, subprocess.TimeoutExpired) as error:
        emit(status="blocked", error=str(error) or type(error).__name__,
             help="Run python3 pilot/pilot.py doctor; see pilot/README.md for prerequisites.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
