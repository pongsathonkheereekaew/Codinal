# Phase 24 evidence — bounded local semantic index

Evidence date: 2026-07-26

## Product result

Codinal now builds, reports, searches, rebuilds, and deletes a persistent local
semantic index per session and approved project root. The desktop project
panel exposes Semantic mode, index status, Index/Reindex, Clear, ranked
results, and one-click project-context capture.

Retrieval uses deterministic sparse hashed feature vectors. The database stores
only vectors, paths, line coordinates, and content hashes; it never stores raw
repository chunks. Every returned match reopens the current regular file
through the bound root, revalidates its digest, and reads the preview from the
current source.

## Privacy, containment, and resource bounds

- Index build: 10-second deadline, 5,000 files, 32 MiB total input, 1 MiB per
  file, 20,000 chunks per root scope, 100,000 chunks globally, 32 scopes, and
  a 128 MiB database budget including WAL/SHM.
- Query: two-second deadline, 256-byte query, 100 results, and at most 256
  sparse vector features per chunk.
- Chunks are bounded to 40 lines and 4 KiB. Symlinks, FIFOs, binaries, ignored
  paths, root-identity changes, oversized files, and stale chunk digests are
  rejected or skipped.
- Database files are private, secure-delete is enabled, rebuilds are
  transactional, cancellation rolls back to the prior index, and explicit
  deletion checkpoints/truncates WAL state before vacuuming.
- Global pressure uses deterministic oldest-indexed scope eviction. Queries do
  not mutate ranking or eviction timestamps.

Schema v1 compatibility requires the exact product table/index SQL, exact
column/primary-key shapes, the single expected cascading foreign key, clean
foreign-key and quick integrity checks, and the configured resource limits.
Unknown, corrupt, symlinked, missing-CHECK, extra-UNIQUE, and extra-FK databases
are recreated without retaining prior bytes.

## Verification

- `./verify.sh`: PASS — 651 Python tests; all Rust, desktop security, shell,
  layout, policy-invariant, and host-install gates passed.
- Phase-focused suite: PASS — 133 tests covering indexing, search coordination,
  sessions, authenticated routes, production runtime, and desktop UI contracts.
- Shutdown regression slice: PASS — 7 approval/interaction route tests.
- Spec review: CLEAN.
- Standards/security review: CLEAN.
- `git diff --cached --check`: PASS.

## Real product surface

The production desktop HTML and JavaScript ran against the authenticated
control plane and an isolated Git worktree. The local index contained 4,461
chunks. Semantic search for `persistent goals evidence ledger` returned 28
ranked matches in 208 ms.

The top five included:

`harness-flow/docs/evidence/phase22-persistent-goals.md:1`

The search layout reserved a visible, scrollable result viewport even in a
720-pixel-high window. Selecting the top result added
`desktop/ui/startup.js` to the composer as a fingerprinted File context chip.

## Packaged artifact

- App:
  `desktop/src-tauri/target/release/bundle/macos/Codinal.app`
- Phase artifact:
  `desktop/src-tauri/target/release/bundle/Codinal-0.1.0-phase24-macos-arm64.zip`
- Size: 91,000,711 bytes
- SHA-256:
  `e6b6bc407b017b8587072d243261fe56fea2266eb5b7addde5dd585f207a2d81`
- ZIP integrity: PASS
- Packaged-app smoke: PASS
- `codesign --verify --deep --strict`: PASS
- Signing authority:
  `Developer ID Application: Pongsathon Kheereekaew (BL28MB2PM9)`

This local artifact is signed but is not notarized, stapled, tagged, pushed, or
published.
