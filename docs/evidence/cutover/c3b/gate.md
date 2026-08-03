---
stage: C3b
owner: release engineering
dependencies: [C0, C1, C2a]
status: pending
---

# C3b Rust-only release gate

Required evidence is a fresh macOS package install/upgrade/rollback run with
signature, notarization, staple, process/resource, and SBOM inspection. The
rollback offered to users must be schema-compatible; incompatible recovery
uses the explicit backup contract.

Stop condition: any Python/Tauri/WebView runtime artifact or incompatible
rollback path.

Deterministic implementation result: the filtered `aarch64-apple-darwin`
CycloneDX SBOM generator and Rust-only bundle audit pass against a temporary
app fixture; release scripts pass `bash -n`. The macOS signed/notarized
install, upgrade, Gatekeeper, and schema-compatible rollback run remains
required before this gate can pass.

Local release result (2026-08-02): a fresh
`CODINAL_REQUIRE_SIGNING=1` build using the available Developer ID identity
completed after the C2–C5 source changes; `bash scripts/audit-rust-release.sh`,
`scripts/measure-rust-release-artifacts.sh`, and
`scripts/smoke-macos-release.sh` passed. The canonical `bash verify.sh` also
passed. `codesign -dvvv` reports hardened runtime flags, the Developer ID
Application certificate chain, Team ID `BL28MB2PM9`, and a timestamp. `otool
-L` inspection found only system frameworks and `/usr/lib` libraries. This is
a signed local candidate, not the required notarized install/upgrade/rollback
evidence, so the gate remains pending.

Read-only distribution checks on the current signed candidate (2026-08-02)
make the blocker explicit: `spctl --assess --type execute --verbose=4`
rejected it with `source=Unnotarized Developer ID` (exit 3), and
`xcrun stapler validate` reported no stapled ticket (exit 65). No notarization
submission or external release credential was used.
The exact `scripts/smoke-macos-gatekeeper.sh` wrapper also failed closed at
staple validation with exit `65` before launching the temporary app copy.
The documented `codinal-release` notary profile is also absent: read-only
`xcrun notarytool history --keychain-profile codinal-release` exited `69` with
no Keychain password item.

Fresh local compatibility checks (2026-08-02): release manifest generation now
emits `schema.min_readable=1` and `schema.max_readable=1`; the native updater
rejects incompatible ranges before install and its updater unit suite passed
`9 tests`. Release-contract/update-manifest Python tests passed `6 tests`.
The exact isolated `installs_and_rolls_back_atomically` updater test and the
incompatible-schema test each passed again after the signed rebuild. The
current package smoke also passed against the rebuilt app archive. A fresh
temporary extraction of `Codinal-0.1.0-macos-arm64.zip` then passed the
Rust-only audit and packaged process smoke without touching `/Applications`.
The new opt-in archive-level updater test also passed with the real
`.app.tar.gz` artifact:

```text
CODINAL_RELEASE_ARCHIVE="$PWD/desktop/gpui/target/release/bundle/Codinal-0.1.0-macos-arm64.app.tar.gz" CODINAL_RELEASE_VERSION=0.1.0 cargo test --manifest-path desktop/native-host/Cargo.toml installs_and_rolls_back_the_actual_release_archive -- --ignored --nocapture
```
The previously installed `/Applications/Codinal.app` passed
`audit-rust-release.sh` and packaged launch/process smoke. At that earlier
checkpoint the current signed candidate had not yet been installed over it;
signed distribution notarization/stapling, Gatekeeper assessment, fresh
upgrade, and schema-compatible rollback remained pending.

Latest packaged candidate recheck (2026-08-02): the rebuilt bundle was copied
to `/Applications/Codinal.app` after moving the previous bundle and stale
runtime lock to `/tmp/codinal-app-backup-ui.Ln7NNu` for recovery. The installed
binary hash is
`9a9bcceb68c8536b1c7ebcd8f1430014341f2caca62ea098bdd1d3a18b67baaf`,
`bash scripts/audit-rust-release.sh /Applications/Codinal.app` passed,
codesign verification passed, and the packaged process smoke passed. This is
fresh install/process evidence for the rebuilt candidate, not upgrade,
notarization, stapling, Gatekeeper, or rollback evidence. The OpenCode live UI
launch is currently paused at the macOS Keychain re-authorization dialog.

Superseding Developer ID recheck (2026-08-02): the release was rebuilt with
`CODINAL_REQUIRE_SIGNING=1` and the available identity
`Developer ID Application: Pongsathon Kheereekaew (BL28MB2PM9)`. The bundle
reports hardened runtime, Team ID `BL28MB2PM9`, and a timestamp; the signed
Rust-only audit, installed-app codesign verification, and full packaged process
smoke passed. The installed binary hash is
`73df766c6c3f161541059675dda009a8cfcad959a45d7502df6924e0c59e6558`. The
new signed bundle still pauses at the OpenCode Keychain authorization dialog;
notarization, stapling, Gatekeeper, upgrade, and rollback remain unproven.

The bundled runtime now receives its owning desktop PID and uses an event-driven
macOS `kqueue` process-exit watcher. Two live TERM tests and packaged smoke
confirmed that the child runtime exits with its app and leaves no orphaned
writer process.

A previously verified local candidate was installed at
`/Applications/Codinal.app` on 2026-08-02. Its desktop and runtime binary
hashes matched that candidate's release bundle, the Rust-only audit and ad-hoc
signature verification passed in place, and `/Applications` contained one
Codinal bundle. A final installed-app TERM test removed both parent and child
processes before the installed app was relaunched. Authenticated health after
relaunch reported runtime `ready`, migration `verified`, writer lock `held`,
and event store ready; Run remained disabled only because no provider
credential was configured. This is installed-app smoke, not a fresh upgrade of
the current signed candidate. Superseded local builds were moved to Trash and
remain recoverable.

Artifact checksums (fresh Developer ID-signed, not notarized package, 2026-08-02):

```text
eb07387b27b3914ce6040a5dc9fd6c7330967f01c428e42ea34d88d156af86bb  Codinal-0.1.0-macos-arm64.zip
aefe84a996c593c6639caf63d9ea63cd68b878774c68e493b1843429b241d7ba  Codinal-0.1.0-macos-arm64.app.tar.gz
cbb82b03aa390782d3fdb977c19b66b69c4d7001c68063bdd9cd4819576ccd34  Codinal.app/Contents/MacOS/codinal
e26580400a8071ed2a36f21f1b9d472bb9088e9dc0242c3d06a57df0dfcb971f  Codinal.app/Contents/Resources/codinal-runtime
f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9  Codinal.app/Contents/Resources/Codinal-rust-sbom.json
```

Latest rebuilt candidate checksums:

```text
5ae3aad82c9b916b963cb8ddd11cf6b18a19eb47aca141ebe4f6f6260cd9a49b  Codinal-0.1.0-macos-arm64.zip
d15f53449988321f9ab2b185ca7299b729c11662330a842e4732114cb51d7370  Codinal-0.1.0-macos-arm64.app.tar.gz
9a9bcceb68c8536b1c7ebcd8f1430014341f2caca62ea098bdd1d3a18b67baaf  Codinal.app/Contents/MacOS/codinal
f73dd57b33abd27d1a2f8a7d91d89eec6f25dfa5bcfb4a284907282dfc11b4bd  Codinal.app/Contents/Resources/codinal-runtime
f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9  Codinal.app/Contents/Resources/Codinal-rust-sbom.json
```

Latest Developer ID-signed candidate checksums:

```text
62a3b59c132b025cb8070e15cca9e75ea8530d12a9b54423fba3b2168ee2e251  Codinal-0.1.0-macos-arm64.zip
25e85a539484cfcc72ade83bfcee41ca71b6a2ea7f299d150e5a64788045249c  Codinal-0.1.0-macos-arm64.app.tar.gz
73df766c6c3f161541059675dda009a8cfcad959a45d7502df6924e0c59e6558  Codinal.app/Contents/MacOS/codinal
21895107a3446dab7d108c4162badfdab31ce7cd92849b5f54ce6d6be889a60b  Codinal.app/Contents/Resources/codinal-runtime
f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9  Codinal.app/Contents/Resources/Codinal-rust-sbom.json
```

Source checksums:

```text
36b12ab288b6ea97228156ccff61391810e98b7c050d035d7882099f315e1653  scripts/generate_rust_sbom.py
fef46b02c6903ebd6329db9fccc01e85aaf39ba255bba8e1cd58ea2419ebb0f4  scripts/audit-rust-release.sh
512bf790d954939b7eda0d9404a39d19e7a19e80df22843eee119152856df421  scripts/build-macos-release.sh
83d4f53ab2816a2005e7edd49170fbc2386a71d105becbb2bc23f82ad7af6251  NOTICE
573fcce86dc2a200ad1368106a032ec7debecedfd1562741e105717fdd79abc3  desktop/native-host/src/host.rs
aabebb4b31ed726e444d99d0f5bb5242ca9873e4c3e6467914667263a32529e7  crates/codinal-runtime/src/parent_watchdog.rs
d18387f2de79d299c38ff40a2695e826a9794e36742a020a5a5bf79d1ecf36e4  scripts/generate_update_manifest.py
d490e8389e4869365bb58114df7c57bf88813e086849b1df77c05156a117b980  desktop/native-host/src/updater.rs
```

Fresh signed-candidate recheck (2026-08-03): the release bundle and the
installed `/Applications/Codinal.app` contain matching desktop and runtime
hashes (`2216d5d1c5687afa6c27d8cd34db4b89a8d47b3cc68152d080ae4ae9d88bc616`
and `54b4b796652ace072a454a842da2b5dc188dc2f54069f6c52a213eb48eecfe53`).
`codesign --verify --deep --strict` and `bash scripts/audit-rust-release.sh`
passed, and the full `bash verify.sh` gate passed. The current distribution
blockers are unchanged and were rechecked: `xcrun stapler validate` exits `65`
because no ticket is stapled, `spctl` exits `3` with
`source=Unnotarized Developer ID`, and `xcrun notarytool history
--keychain-profile codinal-release` exits `69` because the profile is absent.
Therefore C3b remains `pending`; this is signed local-candidate evidence, not
notarized distribution or a fresh installed upgrade/rollback run.

Latest archive checksums:

```text
e17fa7e8c9b83d7afe62dea52ff08f1d6b68bcb15b2997232da1b8fc5146fce4  Codinal-0.1.0-macos-arm64.zip
01a80a4e449bc42706e4178abb730e104b7ea8fa1d9b140ea197590ae3dcc823  Codinal-0.1.0-macos-arm64.app.tar.gz
2216d5d1c5687afa6c27d8cd34db4b89a8d47b3cc68152d080ae4ae9d88bc616  Codinal.app/Contents/MacOS/codinal
54b4b796652ace072a454a842da2b5dc188dc2f54069f6c52a213eb48eecfe53  Codinal.app/Contents/Resources/codinal-runtime
f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9  Codinal.app/Contents/Resources/Codinal-rust-sbom.json
```

Final cost-estimator candidate (2026-08-03): the signed bundle rebuilt after
the DeepSeek cache-cost correction has matching archive and installed hashes:

```text
41abece8e5abcc637eec9f8e07fde807d248f5add6609e07724e25d5731cc2bb  Codinal-0.1.0-macos-arm64.zip
3de04b195ce07bb180fc1e2bcb5b3d6f885073978b70379dd360060ec46b1bae  Codinal-0.1.0-macos-arm64.app.tar.gz
80e42ea5f23451a0ef6b505696b7037aafb8ffc1ee4055363c6c5e841db5af91  Codinal.app/Contents/MacOS/codinal
7fe95d9f054bae9faef2fd03963c7996c79e5711aaefb61465bbace62ae4e8cc  Codinal.app/Contents/Resources/codinal-runtime
f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9  Codinal.app/Contents/Resources/Codinal-rust-sbom.json
```

The release build, Rust-only audit, codesign verification, installed process
launch, and full verifier passed for this candidate. Notarization, stapling,
Gatekeeper acceptance, and a fresh installed upgrade/rollback remain pending
because the Apple notary profile is absent and the candidate is explicitly
unnotarized.

Fresh UI-focus candidate (2026-08-03): the signed package was rebuilt after
adding root-level Tab/Shift-Tab focus traversal and installed at
`/Applications/Codinal.app`. Bundle/archive hashes matched the installed
candidate:

```text
1188d07f3cc45f11055671dff842a1aa359c187b1faf9063ae0653e1348014fc  Codinal-0.1.0-macos-arm64.zip
7addae568ec97a92733353eac54474b1ba1e78235b2f9dbedc4e065e28b3ff61  Codinal-0.1.0-macos-arm64.app.tar.gz
987638b3ea6f35d3fb9201ab5d775c1c53837b3c6f60625b5138139bdf57f35f  Codinal.app/Contents/MacOS/codinal
18f618e08f126dbc601bca2f6d3bfab8d59e30e12231d8c6f3fb3fc483a408ec  Codinal.app/Contents/Resources/codinal-runtime
f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9  Codinal.app/Contents/Resources/Codinal-rust-sbom.json
```

Audit, deep strict code-sign verification, installed launch, GPUI `87/87`,
and the full `bash verify.sh` gate passed. This refresh changes only the
signed local candidate evidence; the notarization, stapling, Gatekeeper, and
fresh upgrade/rollback blockers remain unchanged.

Current-candidate archive updater recheck (2026-08-03): the exact
`.app.tar.gz` produced by the UI-focus build was exercised by
`installs_and_rolls_back_the_actual_release_archive`; the ignored updater test
passed `1/1`. The current bundle also passed `scripts/smoke-macos-release.sh`
and `scripts/audit-rust-release.sh`. This closes the locally actionable
archive-level upgrade/rollback gap; it does not replace the required notarized
installed-app upgrade/rollback run.

Current installed-candidate distribution recheck (2026-08-03) recorded the
same external-state failures: `xcrun notarytool history --keychain-profile
codinal-release` exited `69` because the profile has no Keychain password item;
`xcrun stapler validate /Applications/Codinal.app` exited `65` because no
ticket is stapled; and `spctl --assess --type execute --verbose=4` exited `3`
with `source=Unnotarized Developer ID`. These are release-authority blockers,
not Rust package or local audit failures.

Latest installed candidate refresh (2026-08-03): the signed release was
rebuilt after the focus/accessibility patch and installed at
`/Applications/Codinal.app`. Bundle and installed desktop hashes match at
`19cf3b026a4bdb3f3bc0ef3a54b627595811309257e0d3f1b65dbc78e4915a02`; the
runtime resource hash is
`8f7f8c71f6f483af997bef0acc170360607f6edc848184256a98bb863e238d21`.
After stopping the prior running instance to avoid the single-instance smoke
collision, `scripts/smoke-macos-release.sh /Applications/Codinal.app` passed;
the app was then relaunched. The exact current `.app.tar.gz` passed
`installs_and_rolls_back_the_actual_release_archive` (`1/1`). The notary
profile, stapling, and Gatekeeper results remain `69`/`65`/`3` as above.

Current signed candidate recheck (2026-08-03): the release and installed
desktop hashes now match at
`d3afa61f734036a18dc2d7b68cbf5f1aa237db9be0bb2a5ce893423821eb1f8e`; runtime
resource hashes match at
`575b67e0d0dfca8e4a9ecdb8ca0cc53cabb8926b7aa8397baf1c5e591c7febd2`, and the
SBOM hash remains
`f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9`. Deep
strict codesign verification, Rust-only audit, packaged smoke, installed-app
smoke, and exact archive install/rollback (`1/1`) passed. Notarization is
still blocked by the absent Keychain profile (`69`), missing stapled ticket
(`65`), and Gatekeeper's `source=Unnotarized Developer ID` (`3`).

Current external-state recheck (2026-08-03): `xcrun notarytool history
--keychain-profile codinal-release` again exited `69`, `xcrun stapler validate`
exited `65`, and `spctl --assess` exited `3` with
`source=Unnotarized Developer ID`. These remain release-authority blockers;
the local signed package and archive rollback evidence remain green.

Latest signed candidate recheck (2026-08-03): the app-level focus-action and
bounded-Keychain-startup changes rebuilt and installed successfully. Bundle and
installed desktop hashes match at
`af738dbdb3fd66a23e973e4b4e7c13c57558aba21fac9dd350571e9eabe05476`; the
runtime resource hash is
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`, and the
SBOM hash is
`f4e551e79053c4de23892b8da7652b715d297ab1b293a19c7e2e2872952d39e9`.
`scripts/smoke-macos-release.sh /Applications/Codinal.app`,
`scripts/audit-rust-release.sh`, deep strict code-sign verification, and the
exact archive install/rollback test (`1/1`) passed. Notarization remains
blocked by notary profile `69`, stapler `65`, and Gatekeeper `3`; no notarized
upgrade/rollback claim is made.

Latest installed release after startup-truth correction (2026-08-03): bundle
and installed desktop hashes match at
`2bcf5991893e6b93e6771bee65385b8c9e2ce6726da0dab9e23de6f3ecf700a9`; runtime
resource hash is
`74f18cb09e629b7a72e547b9e3afc7434b8b825bdbe16d5b78300d6204d59893`.
Installed-app smoke, Rust-only audit, deep strict codesign, and the exact
archive install/rollback test (`1/1`) passed. Apple notarization/stapling and
Gatekeeper evidence remain blocked at the previously recorded `69`/`65`/`3`.

Fresh external release recheck (2026-08-03): `xcrun notarytool history
--keychain-profile codinal-release` exited `69` because the credential profile
is absent; `xcrun stapler validate /Applications/Codinal.app` exited `65`
because no ticket is stapled; and `spctl --assess --type execute` exited `3`.
The local signed artifact remains installable and verified, but no Apple
notarized distribution claim is made.

Latest installed candidate after the DeepSeek probe-budget correction
(2026-08-03): bundle and installed desktop hashes match at
`5e738590b634ae6b69e844711d579203c65c39c0e703e9a235f4d7a42c19b976`; runtime
resource hashes match at
`4e2ff1e1859291ccf0c1f5303b191cbbb0f0d977eb9804b370fbe9c16ef7019c`.
Packaged smoke, installed-app smoke, Rust-only audit, deep strict codesign,
and the exact current archive install/rollback test (`1/1`) passed. Current
archive hashes are:

```text
3ccfc4f7b8f248d4545f59b185a07ae1ea403c80cdd0e21820170906d01ab48e  Codinal-0.1.0-macos-arm64.zip
60a5906fa579ed04ee0cf32f388eebfb6a056ccbdeb6460db6a9029dc343d45a  Codinal-0.1.0-macos-arm64.app.tar.gz
```

Notarization remains blocked by the absent profile (`69`), missing stapled
ticket (`65`), and Gatekeeper rejection (`3`).

Fresh external-state recheck (2026-08-03): `xcrun notarytool history
--keychain-profile codinal-release` again exited `69` with no Keychain
password item for the profile. The installed app has no stapled ticket
(`xcrun stapler validate` exit `65`), and `spctl --assess --type execute`
continues to reject it (exit `3`). No notarized release claim is made.

Latest signed UI candidate recheck (2026-08-03): the rebuilt visual-pass
bundle was installed at `/Applications/Codinal.app`. Packaged/installed smoke,
Rust-only release audit, deep strict codesign verification, and the exact
`.app.tar.gz` install/rollback test passed (`1/1`). The installed desktop hash
is `25819a982620a982c6e7bc6d80555a59b065f49d578f3d5724451b3f2566113e` and
the runtime resource hash is
`4e2ff1e1859291ccf0c1f5303b191cbbb0f0d977eb9804b370fbe9c16ef7019c`.
Read-only external checks again returned notary profile `69`, stapler `65`,
and Gatekeeper `3`; notarized installed upgrade/rollback evidence remains
unavailable, so C3b stays pending.
