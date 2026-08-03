# GPUI (codinal) vs comet-native comparison (status 2026-08-01)

## 1) สถาปัตยกรรม / process model
- comet: one binary with headed/main UI + optional `comet headless`, typed in-process/IPC RPC with same protocol across frontends (UI + TUI + headless worker), and durable multi-device room topology.
- codinal GPUI: Rust desktop shell is functional as UI runtime, but control plane is still HTTP-focused and tied to local runtime process ownership semantics.
- สรุป: codinal ยังยังไม่ถึงระดับ `frontends share protocol` ของ comet ในตอนนี้.

## 2) Routing/transport parity
- comet: typed RPC + stream/event model, same schema shared across shell/daemon/TUI.
- codinal: runtime HTTP endpoints are moving into Rust by slices; shell still prototype and relies on control-plane client bindings, not a shared typed transport contract.
- สรุป: GPUI ของเรายังไม่เท่าคอมป์เทียบกับเรื่อง protocol unification.

## 3) Shell behavior / render performance
- comet: explicit event-loop optimization, transcript memoization, coalesced redraws, and deterministic attach/detach semantics in TUI.
- codinal GPUI: already has sessions/transcript/approvals/terminal primitives but no formal benchmark contract for scroll/cached transcript/predictable backpressure, and no dual frontends.
- สรุป: GPUI ยังยังเป็นร่างที่ใช้งานได้ แต่ยังไม่ถึงระดับ production smoothness ของ comet.

## 4) คัดลอกได้ทันทีไหม
- คัดลอกได้ (safe):
  - shell + engine split mindset (`headed` + `headless` target)
  - typed command bus/transport abstraction before implementation
  - render optimization patterns (memoized transcript rows / coalesced events)
- คัดลอกไม่ครบ/ไม่แนะนำตอนนี้:
  - comet’s Loro/DO/R2 stack (ใหญ่เกิน scope)
  - exact protocol schemas (แตกต่าง route surface)
  - full room/sync model (ต้อง migration design ใหม่)
