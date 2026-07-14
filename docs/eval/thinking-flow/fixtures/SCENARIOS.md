# Fixtures

## S1 — finalize-plan skill?

User: “ควรมี skill `finalize-plan` ที่รัน grilling แล้ว scrutinize ก่อนส่งแผนไหม หรือแค่ปรับ description?”

Constraints: harness-flow + `~/.agents`; prefer Matt; keep AGENTS thin; `ask-matt` has `disable-model-invocation: true`.

## S2 — default grilling for every feature?

User: “อยากให้ทุกฟีเจอร์เริ่มด้วย grilling + wayfinder เสมอ จะได้คิดดีแบบ Fable”

Constraints: must not destroy token efficiency; Matt distinguishes fog vs one-session ideas.

## S3 — install backup noise

User: “`AGENTS.md.bak.*` จะรก; ควร auto-delete หลัง N วันหรือไม่ให้ backup เลย?”

Constraints: `install.sh` currently backups on diff then overwrites; footgun was silent overwrite.
