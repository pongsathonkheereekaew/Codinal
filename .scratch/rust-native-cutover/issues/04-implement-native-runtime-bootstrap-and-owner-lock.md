Type: task
Status: resolved
Blocked by: 02

## Question

Can `codinal-runtime` ship a process bootstrap that consumes the three native
launch environment values, acquires an exclusive data-directory owner lock,
binds the authenticated loopback health route, and releases the lock on a
clean shutdown?

## Answer

Yes. `codinal-runtime` now exposes a `codinal-runtime` executable and startup
bootstrap. It consumes `CODINAL_SESSION_TOKEN`, acquires an OS-released
exclusive `.codinal-runtime.lock`, and serves the authenticated loopback health
route. Per-connection parse, disconnect, and timeout errors do not terminate
the listener or release the owner lock; listener accept failures remain fatal.

Verification: all five Rust crate suites pass (24 unit/integration tests), the
runtime executable builds, and `clippy -D warnings` passes. The executable
regression test proves a malformed loopback connection is followed by a valid
authenticated health request.
