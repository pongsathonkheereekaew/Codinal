---
name: insurance-commission
description: "Calculate insurance commission from plan name + premium. Accepts any input format (Thai/English plan name, code, image). Outputs commission rate table by policy year + commission amount in ฿. Source: Tokio Marine CMK025/2026 (updated 13 May 2026)."
---

# /insurance-commission

Calculate commission rate + amount for Tokio Marine insurance plans.

## Input (any format accepted)
- Plan name (Thai or English) or plan code
- Annual premium (฿)
- Optional: entry age, sum assured, policy year number

## Output format
Table with policy year → commission rate → commission amount.

## Workflow

- [ ] **Step 1** — Parse plan name/code → match to REFERENCE.md table
- [ ] **Step 2** — Ask if missing: entry age, sum assured tier (if plan needs it)
- [ ] **Step 3** — Look up commission rates by SA tier + age group
- [ ] **Step 4** — Calculate commission amount = premium × rate per year
- [ ] **Step 5** — Output table + notes on production count

## Step 1 — Plan matching rules

| Input contains | Match |
|---|---|
| **Whole Life / ตลอดชีพ** | |
| WL17 / Simple Life 10 / ซิมเพิล 10 | WL17 |
| WL18 / Simple Life 15 / ซิมเพิล 15 | WL18 |
| WL19 / Simple Life 20 / ซิมเพิล 20 | WL19 |
| WL20 / Simple Life 90 / ซิมเพิล ครบ 90 | WL20 |
| WL21 / All Life 10 / ออล ไลฟ์ @90/10 | WL21 |
| WL23 / All Life 20 / ออล ไลฟ์ @90/20 | WL23 |
| WL24 / All Life @90/@60 / ออล ไลฟ์ @90/@60 | WL24 |
| WLP5 / Whole Life Plus @90/5 / โฮล ไลฟ์ พลัส @90/5 | WLP5 |
| WLP6 / Whole Life Plus @90/10 / โฮล ไลฟ์ พลัส @90/10 | WLP6 |
| WLE1 / Whole Life Plus Extra @90/15 / โฮล ไลฟ์ พลัส เอ็กซ์ตร้า @90/15 | WLE1 |
| WLE2 / Whole Life Plus Extra @90/20 / โฮล ไลฟ์ พลัส เอ็กซ์ตร้า @90/20 | WLE2 |
| HV1N / Tokio High Value @85/10 / ไฮ แวลู 85/10 | HV1N |
| HV2N / Tokio High Value @85/@85 / ไฮ แวลู 85/85 | HV2N |
| EL1N / Easy Life @90/5 / อีซี ไลฟ์ @90/5 | EL1N |
| EL2N / Easy Life @90/10 / อีซี ไลฟ์ @90/10 | EL2N |
| EL3N / Easy Life @90/15 / อีซี ไลฟ์ @90/15 | EL3N |
| EL4N / Easy Life @90/20 / อีซี ไลฟ์ @90/20 | EL4N |
| HL1N / Happy Life @90 / แฮปปี้ ไลฟ์ @90 | HL1N |
| **Endowment / สะสมทรัพย์** | |
| EN10 / Endowment 10 / สะสมทรัพย์ 10 | EN10 |
| EN15 / Endowment 15 / สะสมทรัพย์ 15 | EN15 |
| EN20 / Endowment 20 / สะสมทรัพย์ 20 | EN20 |
| EN55 / Endowment at 55 / สะสมทรัพย์ ครบ 55 | EN55 |
| EN60 / Endowment at 60 / สะสมทรัพย์ ครบ 60 | EN60 |
| HI1N / High Saving 18/6 / ไฮ เซฟวิง 18/6 | HI1N |
| HI3N / High Saving 21/7 / ไฮ เซฟวิง 21/7 | HI3N |
| HI4N / High Saving 21/14 / ไฮ เซฟวิง 21/14 | HI4N |
| HI5N / High Saving 21/18 / ไฮ เซฟวิง 21/18 | HI5N |
| SS3N / Super Saving 21/7 / ซูเปอร์ เซฟวิง 21/7 | SS3N |
| HC1N / Happy Cash 15/8 / แฮปปี้ แคช 15/8 | HC1N |
| HC2N / Happy Cash 20/10 / แฮปปี้ แคช 20/10 | HC2N |
| HC3N / Happy Cash 25/20 / แฮปปี้ แคช 25/20 | HC3N |
| **ภาษี / Tax Saver** | |
| TTS1 / Tax Saver 15/10 / โตเกียว แทกซ์ เซฟเวอร์ 15/10 | TTS1 |
| TTS2 / Tax Saver 15/10 GIO / โตเกียว แทกซ์ เซฟเวอร์ GIO | TTS2 |
| TST1 / Super Tax 10/2 GIO / โตเกียว ซูเปอร์ แทกซ์ 10/2 | TST1 |
| TST2 / Super Tax 10/6 GIO / โตเกียว ซูเปอร์ แทกซ์ 10/6 | TST2 |
| TST3 / Super Tax 10/10 GIO / โตเกียว ซูเปอร์ แทกซ์ 10/10 | TST3 |
| TFB1 / Future Bright 18/5 / โตเกียว ฟิวเจอร์ ไบรท์ 18/5 | TFB1 |
| TFB2 / Future Bright 22/10 / โตเกียว ฟิวเจอร์ ไบรท์ 22/10 | TFB2 |
| **Smart Planning** | |
| 550A / Smart Planning 550/5 / สมาร์ท แพลนนิง 550 จ่าย 5 | 550A |
| 550B / Smart Planning 550/10 / สมาร์ท แพลนนิง 550 จ่าย 10 | 550B |
| 550C / Smart Planning 550/15 / สมาร์ท แพลนนิง 550 จ่าย 15 | 550C |
| 550D / Smart Planning 550/@60 / สมาร์ท แพลนนิง 550 ครบ 60 | 550D |
| 800E / Smart Planning 800/5 / สมาร์ท แพลนนิง 800 จ่าย 5 | 800E |
| 800F / Smart Planning 800/10 / สมาร์ท แพลนนิง 800 จ่าย 10 | 800F |
| 800G / Smart Planning 800/15 / สมาร์ท แพลนนิง 800 จ่าย 15 | 800G |
| 800H / Smart Planning 800/@60 / สมาร์ท แพลนนิง 800 ครบ 60 | 800H |
| **ชั่วระยะเวลา / Term & Monthly Care** | |
| MC4N / Monthly Care / มันท์ลี แคร์ | MC4N |
| LT3N / Level Term / ชั่วระยะเวลา | LT3N |
| LT4N / Tokio Term Life A90/A90 / โตเกียว เทอม ไลฟ์ | LT4N |
| TR3N / Term Rider | TR3N |
| TR4N / Tokio Life Term / ออล ไลฟ์ Term | TR4N |
| TRP3 / Term for Payer | TRP3 |
| **PA / อุบัติเหตุส่วนบุคคล** | |
| PA43-PA48 / Prestige Care / เพรสทิจ | PA43-PA48 |
| PA Plus 1 / K10C / K12C / K13C / K14C / K15C / K25C | PA_PLUS1 |
| PA Plus 2 / HI2B / HI3B / HI5B | PA_PLUS2 |
| **คืนเงิน / Refund** | |
| RP7N / Happy Refund 100% Pay 10 / แฮปปี้ รีฟันด์ 100 จ่าย 10 | RP7N |
| RP8N / Happy Refund 50% Pay 10 / แฮปปี้ รีฟันด์ 50 จ่าย 10 | RP8N |
| RP9N / Happy Refund 100% Pay 15 / แฮปปี้ รีฟันด์ 100 จ่าย 15 | RP9N |
| RP11 / Happy Refund 100 (rider) | RP11 |
| RP12 / Happy Refund 50 (rider) | RP12 |
| SP4N / Solution Design 30/1 / โซลูชั่น ดีไซน์ | SP4N |
| SP5N / Solution Design 30/1 GIO / โซลูชั่น ดีไซน์ GIO | SP5N |
| **เด็ก / การศึกษา** | |
| TCS1 / Tokio Child Shield 18/5 / ชายด์ ชิลด์ 18/5 | TCS1 |
| TCS2 / Tokio Child Shield 22/10 / ชายด์ ชิลด์ 22/10 | TCS2 |
| YC1N / Pension Kid dee 40/5 / เพนชั่น คิดดี 40 จ่าย 5 | YC1N |
| YC2N / Pension Kid dee 40/10 / เพนชั่น คิดดี 40 จ่าย 10 | YC2N |
| YC3N / Pension Kid dee 40/@21 / เพนชั่น คิดดี 40 ครบ 21 | YC3N |
| YC4N / Pension Kid dee 45/5 / เพนชั่น คิดดี 45 จ่าย 5 | YC4N |
| YC5N / Pension Kid dee 45/10 / เพนชั่น คิดดี 45 จ่าย 10 | YC5N |
| YC6N / Pension Kid dee 45/@21 / เพนชั่น คิดดี 45 ครบ 21 | YC6N |
| **บำนาญ / Annuity** | |
| TSA1 / Senior Annuity 70 Pay 5 / ซีเนียร์ แอนนิวิตี้ 70 จ่าย 5 | TSA1 |
| TSA2 / Senior Annuity 70 Pay 10 / ซีเนียร์ แอนนิวิตี้ 70 จ่าย 10 | TSA2 |
| TSA5 / Senior Annuity 75 / ซีเนียร์ แอนนิวิตี้ 75 | TSA5 |
| TPA4 / Perfect Annuity 65 / เพอร์เฟคท์ แอนนิวิตี้ 65 | TPA4 |
| YHA1 / Young Happy Annuity 55 Pay 5 | YHA1 |
| YHA2 / Young Happy Annuity 55 Pay 15 | YHA2 |
| YHA3 / Young Happy Annuity 55 ครบอายุ | YHA3 |
| YHA4 / Young Happy Annuity 60 Pay 5 | YHA4 |
| YHA5 / Young Happy Annuity 60 Pay 15 | YHA5 |
| YHA6 / Young Happy Annuity 60 ครบอายุ | YHA6 |
| YHA7 / Young Happy Annuity 65 / ยัง แฮปปี้ แอนนิวิตี้ 65 | YHA7 |
| PC12 / Pension Prompt Choice 55 / เพนชั่น พร้อม ช้อยส์ | PC12 |
| PN32 / Pension Choice Speedy 50 / สปีดี้ 50 | PN32 |
| PN34 / Pension Speedy 55 / เพนชั่น สปีดี้ | PN34 |
| **ยูนิตลิงค์ / Unit-Linked** | |
| URP1 / Tokio Link / โตเกียว ลิงค์ (basic premium) | URP1 |
| URS1 / Tokio Link regular top-up | URS1 |
| UST1 / Tokio Link single top-up | UST1 |
| URP3 / Tokio Beyond / โตเกียว บียอนด์ (basic premium) | URP3 |
| UST2 / Tokio Beyond single top-up | UST2 |
| USP1 / Tokio Beyond Platinum / โตเกียว บียอนด์ แพลทินัม | USP1 |
| UST3 / Tokio Beyond Platinum single top-up | UST3 |
| **Health Riders** | |
| HS7N / Tokio Smart Health / สมาร์ท เฮลธ์ | HS7N |
| HS6N / Tokio Smart Health Copayment / สมาร์ท เฮลธ์ แบบมีค่าใช้จ่ายร่วม | HS6N |
| HB-N / Hospital Benefit / ค่าชดเชยรายวัน | HB-N |
| HBSP / Super Plan / ซูเปอร์แพลน | HBSP |
| HSGP / Tokio Good Health Prime / กู๊ด เฮลธ์ ไพรม์ | HSGP |
| HSGB / Tokio Good Health Bonus / กู๊ด เฮลธ์ โบนัส | HSGB |
| OPD1 / Out Patient Department / ผู้ป่วยนอก | OPD1 |
| OPD2 / Out Patient Co-Payment / ผู้ป่วยนอก Co-Payment | OPD2 |
| UHSX / Tokio Super Good UDR | UHSX |
| **Disability Riders** | |
| WP-B / WPTR / WP-F / Waiver Premium / ยกเว้นเบี้ยประกันภัย | WP-B |
| PB4N / PB5N / Payer Benefit Rider 4/5 / ผลประโยชน์ผู้ชำระเบี้ย | PB4N |
| TPD3 / Total and Permanent Disability / ทุพพลภาพถาวรสิ้นเชิง | TPD3 |
| T4MC / TPD Monthly Care | T4MC |
| **CI Riders** | |
| FSD2 / Female Special Disease / สตรี ดีซีสส์ | FSD2 |
| CI3N / CI2N / Early CI Care / โรคร้ายแรงเออรี่ ซีไอ แคร์ | CI3N |
| WPCI / Waiver Premium on CI / ยกเว้นเบี้ยกรณีโรคร้ายแรง | WPCI |
| CA1N / Tokio Cancer Care / แคนเซอร์ แคร์ / โรคมะเร็ง | CA1N |
| UCI3 / Early CI Super Care UDR | UCI3 |
| **Accident Riders** | |
| ADBN / ADDN / Accidental Death Benefit / อุบัติเหตุคุ้มครองการเสียชีวิต | ADBN |
| EMEN / Accidental Medical Expense / ค่ารักษาพยาบาลอุบัติเหตุ | EMEN |
| UAIN / URC4 / Accidental Indemnity AI UDR | UAIN |
| UAME / Accidental Medical Expense UDR | UAME |

If plan not found → say "ไม่พบแบบประกันในฐานข้อมูล" and list known plans.

## Step 2 — Required inputs per plan

| Plan | Need SA? | Need Age? | Age range |
|---|---|---|---|
| WL17/18/19 | YES (100k-199k or 200k+) | YES | 0-70 |
| WL20 | YES (250k-499k or 500k+) | YES | 16-70 |
| WL21 | YES (250k-299k / 300k-499k / 500k+) | YES | 0-70 |
| WL23 | YES (250k-299k / 300k-499k / 500k+) | YES | 0-70 |
| WL24 | YES (250k-299k / 300k-499k / 500k+) | YES | 16-54 |
| WLP5/6 | YES (100k-149k / 150k-249k / 250k-499k / 500k-999k / ≥1M) | YES | 0-70 |
| WLE1/2 | YES (≥100k, multiple tiers) | YES | 0-70 |
| EL1N-EL4N | YES (100k-149k / 150k-249k / 250k-499k / 500k-999k / ≥1M) | YES | 0-70 |
| HL1N | YES (100k-249k / 250k-499k / ≥500k) | YES (pay term) | 0-60 |
| EN10/15/20 | YES (100k-499k or ≥500k) | YES | varies |
| EN55 | YES (200k-499k or ≥500k) | YES | 16-44 |
| EN60 | YES (200k-499k or ≥500k) | YES | 16-49 |
| HI1N | YES (100k-299k or ≥300k) | NO | 0-70 |
| HI3N | YES (100k-299k or ≥300k) | NO | 0-70 |
| HI4N | YES (70k-249k / 250k-499k / ≥500k) | YES (66-70 special) | 0-70 |
| HI5N | YES (70k-299k / 300k-499k / ≥500k) | YES (66-70 special) | 0-70 |
| SS3N | YES (100k-299k or ≥300k) | NO | 0-70 |
| HC1N | YES (80k-99k or ≥100k) | NO | 0-65 |
| HC2N | YES (≥80k) | NO | 0-65 |
| HC3N | YES (≥200k) | NO | 25-65 |
| TTS1/2 | YES (≥50k) | YES | 0-65 |
| TST1 | YES (≥100k) | YES | 20-70 |
| TST2/3 | YES (≥24k) | YES | 30-80 |
| TFB1/2 | YES (≥100k) | NO | 0-65 |
| MC4N | YES (<50k or ≥50k) | YES (pay term) | 20-50 |
| LT3N | YES (≥100k) | YES (pay term 5-9 vs 10-59) | 11-70 |
| LT4N | YES (≥100k) | YES | 11-70 |
| 550A-D | YES (100k-499k or ≥500k) | YES | 30-57 |
| 800E-H | YES (100k-499k or ≥500k) | YES | 30-57 |
| YC1N/4N | YES (100k-249k / 250k-399k / ≥400k) | NO | 0-16 |
| YC2N/5N | YES (100k-249k / 250k-399k / ≥400k) | NO | 0-11 |
| YC3N/6N | YES (100k-249k / 250k-399k / ≥400k) | YES | 0-19 |
| PA/Riders | NO | Some | see REFERENCE |
| TSA1 | YES (≥100k) | YES | 55-65 |
| TSA2 | YES (≥100k) | YES | 55-65 |
| TSA5 | YES (≥100k) | YES | 55-65 |
| TPA4 | YES (≥100k) | YES | 30-55 |
| YHA1/2/3 | YES (≥150k) | YES | 20-50 |
| YHA4/5/6 | YES (≥150k) | YES | 20-54 |
| YHA7 | YES (≥150k) | YES | 20-60 |
| PC12 | YES (100k-249k / 250k-399k / ≥400k) | YES | 30-50 |
| PN32 | YES (100k-249k / 250k-399k / ≥400k) | YES | 30-45 |
| PN34 | YES (100k-249k or 250k-399k) | YES | 30-50 |
| TCS1 | YES (≥100k) | YES | 0-5 or ≥6 |
| TCS2 | YES (≥100k) | YES | 0-5 / 6-9 / ≥10 |
| HV1N | YES (100k-2,999k / ≥3,000k) | YES | 20-70 |
| HV2N | YES (100k-2,999k / ≥3,000k) | YES | 20-60 |
| RP7N/8N | YES (≥250k) | YES | 0-60 |
| RP9N | YES (≥250k) | YES | 0-60 |
| SP4N/5N | NO | YES | 0-69 |
| URP1 | YES (≥96k) | NO | 0-70 |
| URP3 | YES (SAM tier: 5-29 / 30-54 / 55-99 / 100-149 / ≥150×) | NO | 0-70 |
| UST1/2/3/URS1/USP1 | NO (top-up/single) | NO | — |

## Step 3-4 — Calculation

```
Commission (฿) = Annual Premium × Commission Rate (%)
```

Show per policy year for all years where rate > 0.

**Annuity plans (TSA/TPA/YHA/PC/PN series)**: commission only Yr1–5, regardless of pay term. Yr6+ = —.

## Step 5 — Output template

Header per plan:
```
[Plan Name] ([Code]) | เบี้ย: X,XXX ฿/ปี | ทุน: X,XXX,XXX ฿ | อายุ: XX ปี | Production: XX%
```

Combined table (one column per plan + รวม):
```
ปี         | [Plan1] rate | [Plan1] ฿ | [Plan2] rate | [Plan2] ฿ | ... | รวม (฿)
-----------|--------------|-----------|--------------|-----------|-----|--------
1          | XX%          | X,XXX     | XX%          | X,XXX     |     | X,XXX
2          | XX%          | X,XXX     | XX%          | X,XXX     |     | X,XXX
...
[pay term] | XX%          | X,XXX     | XX%          | X,XXX     |     | X,XXX
รวม N ปี  |              | X,XXX     |              | X,XXX     |     | X,XXX
```

**Rules:**
- Main policy: show Yr 1–10 individually; if pay term > 10, expand Yr 11–[pay term] individually (riders may still pay)
- Riders: show individual years where rate changes; group as "11+" only when main policy already finished paying
- If plan has no commission for a year: show — | —
- Single plan (no riders): use simple two-column table (rate | ฿) instead
- รวม column = sum of all ฿ columns for that year
- **รวม N ปี row**: sum each plan's ฿ for Yr1–[main policy pay term]; label "รวม [N] ปี"

See [REFERENCE.md](REFERENCE.md) for all rate tables.
