---
name: insurance-premium-finding
description: "Projects next-year Thai P&L from 3+ years of financial statements using 3-year average percentages, then calculates รายจ่ายเพิ่ม (Insurance Premium) sized to reduce corporate income tax by a target % via deductible director insurance premiums. Use when user provides Thai งบการเงิน (financial statements) images or data and asks for financial projections, insurance premium planning, or tax reduction analysis."
---

# /insurance-premium

Project next-year Thai P&L + calculate **รายจ่ายเพิ่ม (Insurance Premium)** to reduce effective tax toward statutory 20%.

## Quick start

User provides: งบการเงิน (image or data) → ask which year to calculate → use actual if available, estimate if not.

```
Input:  งบการเงิน 3+ ปี + ระบุปีที่ต้องการคำนวณ
Output: Full P&L table (actual or estimated) + รายจ่ายเพิ่ม breakdown
```

## Step 0 — Ask year first

**Before calculating**, ask: "ต้องการคำนวณปีไหน?" (which year?)

- If target year data exists in the statement → use **actual numbers**
- If target year is future (not yet in data) → use **3-yr avg estimate**

## Data mode decision

```
actual numbers available for target year?
  YES → use actual P&L values directly, skip Steps 2–3
  NO  → run 3-yr average estimate (Steps 2–3)
```

Both modes proceed identically from Step 4 onward (tax gap + insurance premium).

## Workflow

- [ ] **Step 0** — Ask which year to calculate
- [ ] **Step 1** — Extract historical data into table (value + % of revenue per year)
- [ ] **Step 2** — *(estimate only)* Calculate 3-year average % per line item
- [ ] **Step 3** — *(estimate only)* Apply avg% to projected revenue → full P&L
- [ ] **Step 4** — Tax gap: effective tax rate vs statutory 20% → calc non-deductible
- [ ] **Step 5** — Calculate รายจ่ายเพิ่ม using core formula → per-director breakdown
- [ ] **Step 6** — Output full table with รายจ่ายเพิ่ม highlighted + verification checks

See [REFERENCE.md](REFERENCE.md) for formulas and output template.
See [EXAMPLES.md](EXAMPLES.md) for worked example (2563–2566).

## Key parameters

| Parameter | Default | Notes |
|---|---|---|
| Target tax reduction | 10%/yr | Adjustable: 5%, 15%, 20% |
| Director count | 5 | Use actual count if provided |
| Statutory tax rate | 20% | Thailand corporate standard |
| Projection method | 3-yr avg | Estimate only; skip if actual data used |

## Revenue projection (estimate mode only)

Check image header for YoY growth % → apply to latest year revenue.
If not provided: use 3-yr avg of YoY growth rates.
