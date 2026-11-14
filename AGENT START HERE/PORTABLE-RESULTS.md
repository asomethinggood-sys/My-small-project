# Portable repository delivery

## Ready archive

`AGENT START HERE/continuum-portable.zip`

- 226,914 bytes
- SHA256: `ba2ba02072180bd1632f144fad07521d4b76bc38ea0124722295aa195147b37a`
- 141 source/configuration files plus the generated file-hash manifest.
- Exactly 14 manual/reusable workflows: Start, Stop, build, ten slot entrypoints, shared slot worker.
- No original legacy scheduled workflows, Git credentials/history, SDK binaries, APK fixture, private signing keys or live server credentials.

The archive is ready to import into a public destination repository. No code modifications or beta variables are required afterward. Start beta automatically builds/tests/publishes the APK bound to that destination, then dispatches its ten workers. Stop beta disables/cancels them. Build time/readiness checks are real; this is not instantaneous startup.

## Verification performed

Source delivery commit: `f76acd4`.

Read-only validation run **43633429258** completed successfully. It:

1. Ran nine exporter/control tests with mocked GH operations. Covered exact ten dispatch filenames, stop-during-build generation rejection, partial-activation rollback, stop-before-cancel ordering, public/nondefault repository rejection, manual-only workflow inventory, destination identity, complete file hashes, refusal to overwrite an existing directory, and public control polling without repository API usage.
2. Exported the complete tree independently in CI.
3. Compiled its Android app with `GITHUB_REPOSITORY=portable-fixture/example`, deliberately different from the source repository.
4. Ran JVM/Rust tests including a destination-discovery assertion, debug lint, ARM64 release assembly and release lint.

The fixture APK was intentionally NOT published, because it points to a test identity rather than a usable user repository. The destination Start workflow will build the real destination APK automatically.

The earlier validation run 43633094716 also passed. The original Android 1.0 APK's emulator/packaging evidence remains in BUILD-RESULTS.md; its old fixed discovery addresses are not suitable for a different repository.

## Not claimed

No new destination repository was created or changed here. No Start beta, Stop beta, or ten-server workflow was executed here. The control tests mocked remote API effects; an actual destination activation is still the next agent/operator's task.

Platform permissions, default-branch registration, account quotas, runner geography, public release access and live readiness can still block activation. A workflow cannot bypass an organization's restrictions or promise permanent availability. The prepared import removes manual application/server development, not those external prerequisites.
