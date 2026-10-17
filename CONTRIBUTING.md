# Contributing to Family Finder

Thanks for helping. This project adds find-my-phone features to
[Grid](https://github.com/Rezivure/Grid-Mobile), so most changes are patches against Grid rather
than files in this repository.

## Before you start

- **Search for existing open-source work first.** If a maintained library or app already solves the
  problem (as FMD did for push-based ringing, and `ble_proximity_signal` did for Bluetooth
  proximity), build on it instead of writing it from scratch. Check that its license is compatible
  with AGPL-3.0 (MIT, BSD, Apache-2.0, GPLv3 and AGPL are fine).
- **Open an issue** for anything bigger than a small fix, so the approach can be agreed first.
- **Never contribute code copied or decompiled from closed apps** such as Samsung Find. Studying how
  they behave is fine; copying their code is not.

## Development setup

```bash
python3 pilot/pilot.py doctor
python3 pilot/pilot.py bootstrap
python3 pilot/pilot.py prepare-android --maps-url https://map.mygrid.app/v1/protomaps.pmtiles
python3 pilot/pilot.py build
```

Grid's source lands in `pilot/.local/grid` (git-ignored). Edit it there, then build.

## Making a change

1. Make the change in `pilot/.local/grid`.
2. Add or update tests under `test/` for any logic you change.
3. Run `python3 pilot/pilot.py build`. It must pass: zero analyzer errors, all Flutter tests, APK
   built.
4. Save the change as a patch in `pilot/patches/`. Keep **one concern per patch**, and if it is
   new, add it to the ordered list in `apply_source_fixes()` in `pilot/pilot.py`.
5. Prove the patch stack reproduces your tree from a clean Grid checkout:

   ```bash
   git -C pilot/.local/grid worktree add --detach /tmp/clean HEAD
   sed -i 's/android:label="Grid"/android:label="Family Pilot (Grid)"/' \
     /tmp/clean/android/app/src/main/AndroidManifest.xml
   for p in $(grep -oE '"[a-z0-9-]+\.patch"' pilot/pilot.py | tr -d '"'); do
     git -C /tmp/clean apply "$PWD/pilot/patches/$p" || echo "FAILED: $p"
   done
   git -C pilot/.local/grid worktree remove --force /tmp/clean
   ```

6. Run the tooling tests: `python3 -m unittest discover -s pilot -p 'test_*.py'`.

## Dependencies

Changing `pubspec.yaml` changes the lock. Copy the resolved `pubspec.lock` to
`pilot/locks/grid-flutter-3.47.7.lock`, update `pilot_sha256` and the package lists in
`pilot/locks/manifest.json`, and note the change in `pilot/locks/README.md`. Existing package
versions should not change unless that is the point of the pull request.

## Testing on phones

Unit tests are not enough for this project: test on real devices where you can, and report what you
actually saw. The verified results in [`pilot/README.md`](pilot/README.md) record the device, Android
version and measured numbers. Please follow that style and say clearly what was **not** tested.

Use dedicated test accounts, never real family locations, while testing.

## Pull requests

- Describe what changed, why, and how you tested it (devices, Android versions, results).
- Keep pull requests focused; unrelated fixes go in separate pull requests.
- Don't commit anything from `pilot/.local/`, `pilot/runtime/` (server secrets and test passwords),
  `artifacts/` or `analysis/` beyond the published Grid docs.

## Reporting security issues

Do not open a public issue for a vulnerability, such as a way for a non-contact to see a location or
ring a phone. Contact the maintainer privately through GitHub first.

## License

By contributing you agree that your contributions are licensed under [AGPL-3.0](LICENSE).
