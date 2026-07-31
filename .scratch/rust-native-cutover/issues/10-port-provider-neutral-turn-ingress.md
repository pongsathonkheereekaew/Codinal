Type: task
Status: resolved
Blocked by: 09

## Question

Can a Rust provider-neutral assistant-turn contract validate bounded tool calls
and feed the runtime permission engine/approval broker from an actual provider
adapter without exposing provider secrets or adding a test-only control route?

## Resolution

Rust now owns a bounded provider-neutral assistant-turn contract and a real
loopback Ollama adapter. The in-process turn ingress reads only public-session
context, rejects unknown tools, and submits consequential calls to the live
approval broker. Provider HTTP framing and JSON depth/size/count bounds have
regression coverage; no provider secret crosses the contract. Durable turn
writes and the public mutation route remain deliberately gated on Ticket 11's
R1 migration/recovery proof, so Python-owned data is not dual-written.
