# Reference — Formulas & Output Template

## Step 2: 3-Year Average %

```
avg% = (year_N% + year_N-1% + year_N-2%) / 3
```

Apply each avg% to projected revenue. รายได้รวม = 100% base always.

## Step 4: Tax Gap Analysis

```
effective_tax_rate  = ภาษีเงินได้ / กำไรก่อนภาษี
gap                 = effective_tax_rate − 20%

non_deductible      = gap × กำไรก่อนภาษี
non_deductible%     = non_deductible / รายได้รวม   ← show as negative
```

If gap > 0 → insurance premium strategy applicable.

## Step 5: Core Premium Formula

```
เป้าลดภาษี          = ภาษีเงินได้_projected × target%   (default 10%)

รายจ่ายเพิ่ม (total) = เป้าลดภาษี ÷ 0.20
                     = ภาษีเงินได้ × target% × 5

per director         = รายจ่ายเพิ่ม ÷ N_directors

ภาษีเงินได้ใหม่      = ภาษีเงินได้ − เป้าลดภาษี
```

**Mechanism:** premium paid by company → deductible expense → reduces taxable income → saves `premium × 20%` in tax.

### Verification checks

```
total_premium × 20%          = เป้าลดภาษี                  ✓
เป้าลดภาษี / ภาษีเงินได้       = target% (e.g. 10%)          ✓
SG&A_old + รายจ่ายเพิ่ม       = รายจ่ายรวมส่วนที่เพิ่ม        ✓
```

### 10-year savings

```
ลดภาษีสะสม (10 ปี) = เป้าลดภาษี × 10 = ภาษีเงินได้ × 100%
```

## Step 6: Output Table Template

| รายการ | ประมาณการ | % |
|---|---|---|
| รายได้รวม | — | 100.00% |
| ต้นทุนขาย | — | xx.xx% |
| กำไรขั้นต้น | — | xx.xx% |
| ค่าใช้จ่ายขายและบริหาร | — | xx.xx% |
| ดอกเบี้ยจ่าย | — | 0.00% |
| รวมค่าใช้จ่าย | — | xx.xx% |
| กำไรก่อนภาษี | — | xx.xx% |
| ภาษีเงินได้ | — | xx.xx% |
| กำไรสุทธิ | — | xx.xx% |
| Effective tax rate | xx% | |
| อัตราภาษี | 20% | |
| รายจ่ายที่ไม่สามารถเป็นรายจ่ายทางภาษี | (—) | -x.xx% |
| กำไรสุทธิทางภาษี | — | |
| ภาษีเงินได้ลดลง | 10%/ปี และ — ใน 10 ปี | |
| ภาษีเงินได้ใหม่ | — | |
| **รายจ่ายเพิ่ม (Insurance Premium)** | **—** | |
| กรรมการ N คน × — บาท/คน | | |
| รายจ่ายรวมส่วนที่เพิ่ม | — | xx.xx% (+x.xx%) |

## Insurance type note

ประกันชีวิต/เกษียณ for directors — qualifies as deductible business expense (รายจ่ายที่ยอมรับทางภาษี) under Thai Revenue Code.
