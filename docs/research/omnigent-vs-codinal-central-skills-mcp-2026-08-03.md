# Omnigent vs Codinal: central skills and MCP

วันที่ตรวจ: 2026-08-03

## คำตอบสั้น

ยังตอบว่า “เราดีกว่าทั้งหมด” ไม่ได้

- **Central skills:** Codinal/harness-flow ดีกว่าในแกน SSOT, projection, ownership และ drift detection
  แต่การ enable/disable ยัง enforce ได้จริงหลัก ๆ ที่ OpenCode; host อื่นยังมีสถานะ unverified
- **MCP:** Python runtime ของเราดีกว่าในแกน approval, schema validation, secret redaction, audit และ durable per-session state
  แต่ Omnigent กว้างกว่าในแกน agent-declared MCP, multi-harness/server lifecycle, discovery/retry/cache และ hosted service
- **ช่องว่างหลักของเรา:** ยังไม่มี MCP registry กลางที่เป็น definition SSOT และถูกใช้ร่วมกันโดย Python runtime, Rust runtime และ host adapters

## หลักฐานฝั่ง Codinal

### Skills

1. Repository ระบุชัดว่า git repo เป็น SSOT ของ portable policy และ skills; `~/.agents` เป็น live projection
   (`MANIFEST.md:3-14`, `README.md:14-15`)
2. Skills ถูก classify เป็น `core` กับ `catalog`; skill ใหม่ถูกค้นพบจาก `skills/` โดยไม่ต้องคัดลอก manifest ขนาดใหญ่
   (`harness/config/skills.yaml:3-20`, `harness/scripts/lib/skills.py:1-9`)
3. Host adapters ใช้ native discovery หรือ symlink/external directory แทนการ copy เนื้อหา
   (`harness/scripts/sync-skill-links.sh:1-11`, `harness/scripts/adapters/opencode.py:1-12`)
4. Rust harness มี source bundle, user overlay, live projection และ host projection พร้อม fingerprint, ownership, drift,
   plan, receipt และ rollback (`crates/codinal-harness/src/lib.rs:1-7`, `crates/codinal-harness/src/inventory.rs:231-257`)

ข้อจำกัดที่ต้องพูดตรง ๆ:

- `harness skill disable` บันทึก journal ได้ แต่ native enforcement มีเฉพาะ OpenCode; base adapter รายงาน
  `unsupported` สำหรับ host ที่ไม่มี visibility mechanism (`harness/scripts/harness_skill.py:10-12`,
  `harness/scripts/adapters/base.py:81-86`, `harness/scripts/adapters/opencode.py:261-303`)
- `sync-skill-links.sh` ยัง link skills ทั้งหมดจาก source ไปยัง adapter dirs (`harness/scripts/sync-skill-links.sh:200-229`)
- ดังนั้น SSOT แข็งแรง แต่ “enabled view เดียวกันทุก host” ยังไม่เสร็จ

### MCP

Python runtime มี implementation ที่เป็น policy boundary ค่อนข้างครบ:

- validate transport, URL, command, cwd และ tool filters (`runtime/mcp/config.py:19-107`)
- require explicit approval และจำกัด environment ของ stdio subprocess (`runtime/mcp/client.py:44-65`, `runtime/mcp/client.py:111-163`)
- register remote tools เข้า manifest เป็น `external`/`requires_approval`, จำกัด schema และกันชื่อชนกัน
  (`runtime/mcp/tools.py:36-78`, `runtime/mcp/tools.py:100-144`)
- รองรับ per-session connect/disconnect/enable/disable/recover พร้อม durable store และ audit
  (`runtime/mcp/service.py:44-114`, `runtime/mcp/service.py:216-301`)
- redaction ก่อนส่ง argument ออก MCP transport มี adversarial test (`runtime/mcp/service.py:98-103`,
  `tests/security/test_mcp_exfiltration.py:92-106`)

Rust `ToolGateway` แข็งแรงในฐานะ low-level execution boundary:

- MCP call ต้องผ่าน explicit program allowlist, approval, timeout/interrupt, idempotent receipt และ JSON-RPC validation
  (`crates/codinal-tools/src/lib.rs:447-550`, `crates/codinal-tools/src/lib.rs:878-1010`)
- process environment ถูก clear เหลือค่าที่อนุญาต และ output ถูกจำกัด/ทำ digest
  (`crates/codinal-tools/src/lib.rs:73-93`, `crates/codinal-tools/src/lib.rs:921-934`)

ข้อจำกัดสำคัญ:

- `ToolConfig::for_workspace()` เริ่มด้วย `mcp_programs` ว่าง; Rust path ยังไม่มี server/session lifecycle แบบ Python
  (`crates/codinal-tools/src/lib.rs:158-188`)
- Rust runtime เปิด MCP executor ผ่าน experimental flag และ session MCP lifecycle routes บางส่วนยังเป็น `501`
  (`crates/codinal-runtime/src/lib.rs:772-782`, `crates/codinal-runtime/src/lib.rs:2575-2766`)
- มี `runtime/integrations/catalog.py` ที่ทำ filesystem เป็น canonical catalog และมี `assets.mcp` ใน integration manifest
  แต่ยังไม่พบการเชื่อม catalog นี้เข้า `MCPService` เป็น registry กลางที่ใช้งานจริง
  (`runtime/integrations/catalog.py:34-57`, `runtime/plugins/translator.py:246-299`)

## หลักฐานฝั่ง Omnigent

- Agent YAML รวม harness/model, tools, sub-agents, OS access และ policies ไว้ใน declaration เดียว
  ([Agent YAML spec](https://github.com/omnigent-ai/omnigent/blob/main/docs/AGENT_YAML_SPEC.md))
- MCP เป็น first-class tool configuration รองรับ local command/stdio และ remote URL/headers; sub-agent มี executor/model
  ของตัวเองและรับช่วง tool context ได้ ([Agent YAML spec](https://github.com/omnigent-ai/omnigent/blob/main/docs/AGENT_YAML_SPEC.md))
- server layer เก็บ agent specs แบบ durable และมี MCP pool สำหรับ service ที่เป็น multi-tenant
  ([server package](https://github.com/omnigent-ai/omnigent/tree/main/omnigent/server),
  [MCP pool](https://github.com/omnigent-ai/omnigent/blob/main/omnigent/server/mcp_pool.py))
- MCP connection มี discovery cache, reconnect retry และ circuit breaker ในตัว
  ([MCP connection](https://github.com/omnigent-ai/omnigent/blob/main/omnigent/tools/mcp.py))
- Policy engine แยก server-wide, agent และ session; มี ALLOW/DENY/ASK, sandbox และการบล็อก skills
  ([Policies](https://github.com/omnigent-ai/omnigent/blob/main/docs/POLICIES.md))
- แต่ `.claude/skills` ใน repository เป็นชุด developer/test skills; จาก Agent YAML spec ไม่พบโมเดล portable
  cross-host skill distribution แบบ `harness-flow` จึงไม่ควรนับว่า Omnigent ชนะ central skills โดยอัตโนมัติ
  ([Omnigent skills directory](https://github.com/omnigent-ai/omnigent/tree/main/.claude/skills))

## ข้อสรุปเชิงออกแบบ

### สิ่งที่เราดีกว่า

1. **Governed SSOT:** definition/projection/ownership/drift ชัดกว่า
2. **Local consequence boundary:** approval, redaction, bounded output และ receipt/audit เหมาะกับงานที่ต้องพิสูจน์ย้อนหลัง
3. **Host projection discipline:** ไม่ต้อง copy skill content ซ้ำหลายที่

### สิ่งที่ Omnigent ดีกว่า

1. **Breadth:** model/harness/tool/MCP declaration เดียวและ server-side orchestration กว้างกว่า
2. **MCP operations:** discovery, reconnect, cache, circuit breaker และ multi-session service ครบกว่าใน path เดียว
3. **Capability conformance:** มี harness bench สำหรับเทียบ declared capability กับ live behavior และรายงาน `DRIFT`
   ([Harness bench design](https://github.com/omnigent-ai/omnigent/blob/main/docs/harness-bench-design.md))

## คำแนะนำเดียว

รักษา `harness-flow` เป็น SSOT แล้วเพิ่ม **MCP registry กลาง** เป็น projection source เดียว:

```text
harness/config/mcp.yaml
  ├─ server id / transport / endpoint-or-command
  ├─ auth reference (ไม่เก็บ secret)
  ├─ tool allow/deny + risk + approval mode
  ├─ host/model requirements
  └─ version / digest / provenance
          ↓
  Python MCPService + Rust ToolGateway + host adapters
```

กติกาที่ควรล็อก:

1. Runtime DB เก็บเฉพาะ user/session state เช่น connected และ enabled; ห้ามกลายเป็น definition SSOT อีกชุด
2. Skill อธิบายวิธีใช้ MCP ได้ แต่ skill ไม่มีสิทธิ์ grant authority
3. ให้ Rust หรือ policy chokepoint เดียวเป็นผู้ตัดสิน call/approval/receipt; Python ทำ orchestration ได้แต่ไม่สร้าง policy อีกชุด
4. เพิ่ม conformance cases ให้ครบ discovery, schema, call, DENY/ASK, secret isolation, timeout, reconnect และ model/host matrix

บทสรุป: **skills ของเราเหนือกว่าในเรื่อง SSOT; MCP ของเราดีกว่าในเรื่อง governance แต่ Omnigent ดีกว่าในเรื่อง breadth และ operational lifecycle.**
จุดชนะที่ควรทำต่อไม่ใช่เพิ่ม MCP integrations แบบกระจาย แต่ทำให้ registry เดียว compile ไปทุก runtime และทุก host.
