# Manual GitHub Actions for Metrolist development

Automatic builds and emulator tests are intentionally disabled to reduce GitHub Actions usage and failure-email noise.

## After code changes

### Build Dudu7 APK

Run **Actions → Build Dudu7 APK → Run workflow** when a completed development change needs an installable APK for the Dudu7 head unit.

The run produces the artifact:

- `metrolist-dudu7-apk`

Do not start a new APK build for every small intermediate commit. Bundle related changes and build once when the implementation is ready for testing.

### Dudu7 UI Smoke Test

Run **Actions → Dudu7 UI Smoke Test → Run workflow** only when changes affect the Dudu7 user interface or interaction flow, especially:

- player layout or controls
- right-side tabs and navigation
- queue return behavior
- library, search, listening history or home screens
- touch behavior and landscape presentation

The default emulator settings match the Dudu7 target: 1280 × 720, 200 dpi, Android 13 / API 33.

The run produces screenshots, video and diagnostics as the artifact `dudu7-ui-test-<run-id>`.

## Normal sequence for a finished change

1. Implement and review the related code changes.
2. Run **Build Dudu7 APK** once.
3. For UI or navigation changes, additionally run **Dudu7 UI Smoke Test** once.
4. Download the APK or test artifact from the completed workflow run.

No workflow should commit run metadata or logs back into the repository.
