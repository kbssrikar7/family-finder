"""Preparation checks only; these are not Grid application or Android tests."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import tarfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import pilot


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / ".local"
        self.source = self.local / "grid"
        for name, value in (("ROOT", self.root), ("LOCAL", self.local), ("SOURCE", self.source)):
            token = patch.object(pilot, name, value)
            token.start()
            self.addCleanup(token.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def source_fixture(self):
        # Deliberately small fixture for transformations, not a copy of Grid.
        files = {
            "pubspec.yaml": "name: fixture\n",
            ".env.example": "MATRIX_SERVER_URL=\nMAPS_URL=\nGAUTH_URL=\nSAT_MAPS_URL=\n",
            "android/app/build.gradle": '\n'.join([
                'plugins { id "com.google.gms.google-services" }',
                'defaultConfig { applicationId "app.mygrid.grid" }',
                "storeFile file(localProperties.getProperty('storeFile'))", "",
            ]),
            "android/app/src/main/AndroidManifest.xml":
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="Grid"/></manifest>',
            "android/app/src/debug/AndroidManifest.xml":
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><uses-permission android:name="android.permission.INTERNET"/><application android:usesCleartextTraffic="true"/></manifest>',
        }
        for name, content in files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        token = patch.object(pilot, "run", return_value=pilot.GRID_COMMIT)
        token.start()
        self.addCleanup(token.stop)

    def test_server_is_private_and_reinitialization_preserves_keys(self):
        pilot.init_server()
        path = self.root / "runtime/data/homeserver.yaml"
        first = path.read_bytes()
        config = json.loads(first)
        self.assertFalse(config["enable_registration"])
        self.assertEqual(config["federation_domain_whitelist"], [])
        self.assertEqual(config["listeners"][0]["resources"][0]["names"], ["client"])
        self.assertEqual(config["ip_range_whitelist"], ["127.0.0.1/32"])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        pilot.init_server()
        self.assertEqual(first, path.read_bytes())

    def test_pilot_has_separate_identity_and_loopback_cleartext_only(self):
        self.source_fixture()
        pilot.prepare_android("https://maps.example.org/region.pmtiles")
        gradle = (self.source / "android/app/build.gradle").read_text()
        self.assertIn('applicationId "app.familyfinder.gridpilot"', gradle)
        self.assertNotIn('id "com.google.gms.google-services"', gradle)
        policy = ET.parse(self.source / "android/app/src/debug/res/xml/pilot_network_security_config.xml").getroot()
        self.assertEqual(policy.find("base-config").get("cleartextTrafficPermitted"), "false")
        self.assertEqual({x.text for x in policy.findall("domain-config/domain")}, {"localhost", "127.0.0.1"})
        debug = ET.parse(self.source / "android/app/src/debug/AndroidManifest.xml").getroot()
        self.assertIsNotNone(debug.find("uses-permission"))
        self.assertNotIn(f"{{{pilot.ANDROID}}}usesCleartextTraffic", debug.find("application").attrib)
        self.assertFalse((self.source / "android/app/src/main/res/xml/pilot_network_security_config.xml").exists())
        self.assertEqual(stat.S_IMODE((self.source / ".env").stat().st_mode), 0o600)
        self.assertIn("\nSAT_MAPS_URL=\n", (self.source / ".env").read_text())
        pilot.prepare_android("https://maps.example.org/region.pmtiles")

    def test_drift_does_not_partially_change_source(self):
        self.source_fixture()
        path = self.source / "android/app/build.gradle"
        path.write_text(path.read_text().replace('applicationId "app.mygrid.grid"', 'applicationId "different"'))
        before = {str(p): p.read_bytes() for p in self.source.rglob("*") if p.is_file()}
        with self.assertRaises(pilot.PilotError):
            pilot.prepare_android("https://maps.example.org/region.pmtiles")
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.source.rglob("*") if p.is_file()})

    def test_existing_environment_is_preserved(self):
        self.source_fixture()
        path = self.source / ".env"
        path.write_text("PRIVATE_SETTING=preserve\n")
        gradle = self.source / "android/app/build.gradle"
        before = gradle.read_bytes()
        with self.assertRaises(pilot.PilotError):
            pilot.prepare_android("https://maps.example.org/region.pmtiles")
        self.assertEqual(path.read_text(), "PRIVATE_SETTING=preserve\n")
        self.assertEqual(gradle.read_bytes(), before)

    def test_env_injection_rejected_before_reading_source(self):
        for url in ("http://example.org/a.pmtiles", "https://example.org/a\nTOKEN=bad", "https://example.org/a b"):
            with self.subTest(url=url), self.assertRaises(pilot.PilotError):
                pilot.prepare_android(url)
        self.assertFalse(self.local.exists())

    def test_wrong_source_revision_is_rejected(self):
        self.source_fixture()
        with patch.object(pilot, "run", return_value="different"), self.assertRaises(pilot.PilotError):
            pilot.prepare_android("https://maps.example.org/region.pmtiles")
        self.assertFalse((self.local / "android-prepared.json").exists())

    def flutter_download_fixture(self, *, bad_checksum=False):
        self.source_fixture()
        archive_buffer = io.BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode="w:xz") as archive:
            data = b"#!/bin/sh\nexit 0\n"
            member = tarfile.TarInfo("flutter/bin/flutter")
            member.size = len(data)
            member.mode = 0o755
            archive.addfile(member, io.BytesIO(data))
        archive_data = archive_buffer.getvalue()
        release = {"hash": "stable-fixture", "version": pilot.FLUTTER_VERSION, "channel": "stable", "dart_sdk_arch": "x64",
                   "archive": "stable/linux/flutter_linux_fixture-stable.tar.xz",
                   "sha256": "0" * 64 if bad_checksum else hashlib.sha256(archive_data).hexdigest()}
        manifest = {"current_release": {"stable": "stable-fixture"}, "releases": [release]}
        base = "https://storage.googleapis.com/flutter_infra_release/releases"
        payloads = {base + "/releases_linux.json": json.dumps(manifest).encode(),
                    base + "/" + release["archive"]: archive_data}

        def download(url, **kwargs):
            # Wrong storage paths fail here, before any extraction assertion.
            return io.BytesIO(payloads[url])

        return download, release

    def test_bootstrap_download_urls_checksum_and_extraction(self):
        download, release = self.flutter_download_fixture()
        with patch.object(pilot.platform, "system", return_value="Linux"), \
                patch.object(pilot.platform, "machine", return_value="x86_64"), \
                patch.object(pilot.shutil, "which", return_value=None), \
                patch.object(pilot.urllib.request, "urlopen", side_effect=download) as request:
            pilot.bootstrap()
            self.assertEqual(request.call_count, 2)
        self.assertTrue((self.local / "flutter/bin/flutter").is_file())
        self.assertEqual(json.loads((self.local / "flutter-release.json").read_text()), release)

    def test_checksum_failure_leaves_source_and_does_not_install_sdk(self):
        download, _ = self.flutter_download_fixture(bad_checksum=True)
        with patch.object(pilot.platform, "system", return_value="Linux"), \
                patch.object(pilot.platform, "machine", return_value="x86_64"), \
                patch.object(pilot.shutil, "which", return_value=None), \
                patch.object(pilot.urllib.request, "urlopen", side_effect=download), \
                self.assertRaisesRegex(pilot.PilotError, "checksum mismatch"):
            pilot.bootstrap()
        self.assertFalse((self.local / "flutter").exists())
        self.assertTrue((self.source / "pubspec.yaml").exists())

    def test_sdk_preparation_copies_packages_without_linking_to_existing_sdk(self):
        origin = self.root / "existing-sdk"
        for relative in ("platforms/android-36", "build-tools/35.0.0", "platform-tools",
                         "licenses", f"ndk/{pilot.NDK_VERSION}"):
            path = origin / relative
            path.mkdir(parents=True)
            (path / "marker").write_text("original")
        with patch.object(pilot, "installed_sdk", return_value=origin), \
                patch.object(pilot, "run") as run:
            sdk = pilot.setup_android_sdk({})
        run.assert_not_called()
        marker = sdk / "platforms/android-36/marker"
        marker.write_text("local change")
        self.assertEqual((origin / "platforms/android-36/marker").read_text(), "original")
        self.assertFalse(marker.parent.is_symlink())

    def test_sdk_missing_download_is_not_mistaken_for_success(self):
        with patch.object(pilot, "installed_sdk", return_value=self.root / "absent"), \
                patch.object(pilot.shutil, "which", return_value="/fake/sdkmanager"), \
                patch.object(pilot.socket, "getaddrinfo", return_value=[]), \
                patch.object(pilot, "run", return_value="No packages installed"), \
                self.assertRaisesRegex(pilot.PilotError, "packages remain missing"):
            pilot.setup_android_sdk({})

    def test_license_rejection_reports_interactive_install_command(self):
        with patch.object(pilot, "installed_sdk", return_value=self.root / "absent"), \
                patch.object(pilot.shutil, "which", return_value="/fake/sdkmanager"), \
                patch.object(pilot.socket, "getaddrinfo", return_value=[]), \
                patch.object(pilot, "run", return_value="Skipping following packages as the license is not accepted"), \
                self.assertRaisesRegex(pilot.PilotError, "license acceptance is required.*sdkmanager.*--install"):
            pilot.setup_android_sdk({})

    def dependency_lock_fixture(self):
        old, new = b"original pinned packages\n", b"reviewed SDK-compatible packages\n"
        locks = self.root / "locks"
        locks.mkdir()
        (locks / "pilot.lock").write_bytes(new)
        (locks / "manifest.json").write_text(json.dumps({
            "lockfile": "pilot.lock", "upstream_sha256": hashlib.sha256(old).hexdigest(),
            "pilot_sha256": hashlib.sha256(new).hexdigest(),
        }))
        self.source.mkdir(parents=True)
        (self.source / "pubspec.lock").write_bytes(old)
        return old, new

    def test_reviewed_lock_is_applied_once_with_original_preserved(self):
        old, new = self.dependency_lock_fixture()
        pilot.apply_dependency_lock()
        pilot.apply_dependency_lock()
        self.assertEqual((self.source / "pubspec.lock").read_bytes(), new)
        self.assertEqual((self.local / "upstream-pubspec.lock").read_bytes(), old)

    def test_custom_dependency_lock_is_not_overwritten(self):
        self.dependency_lock_fixture()
        lock = self.source / "pubspec.lock"
        lock.write_bytes(b"user edits\n")
        with self.assertRaisesRegex(pilot.PilotError, "custom changes"):
            pilot.apply_dependency_lock()
        self.assertEqual(lock.read_bytes(), b"user edits\n")


if __name__ == "__main__":
    unittest.main()
