---
name: nuiny
description: Builds Thai-language insurance sales slide decks (Tokio Marine dark-navy theme) from proposal PDFs (ใบเสนอแบบประกันภัย) using python-pptx. Use when the user mentions nuiny, asks to create sales slides from an insurance quote/proposal PDF, or wants a deck pitching guaranteed returns vs bank deposits with annual cashflow.
disable-model-invocation: true
---

# Nuiny — Insurance Sales Deck Builder

Builds a client-ready sales deck from a Tokio Marine proposal PDF. The pitch targets customers who want returns better than bank deposits plus guaranteed yearly cashflow.

## Workflow

1. **Read the proposal PDF** with the Read tool. Extract: client name/age, plan name (e.g. Happy Cash 15/8), sum assured, premium per year and payment period, yearly cashback, cumulative cashback, cash surrender values, death benefits, maturity benefit, totals, quote number, agent details, quote date.
2. **Compute guaranteed IRR** from actual cashflows (premiums at start of year, benefits at end of year), and the equivalent pre-tax bank rate = IRR / 0.85 (15% withholding tax). Bisection on NPV is enough:

```python
cf = [0.0] * (n_years + 1)
for y in range(pay_years): cf[y] -= premium
for y in range(1, n_years): cf[y] += cashback
cf[n_years] += maturity + cashback_final
# bisect r in [0, 0.10] until NPV ~ 0
```

3. **Build the deck** with python-pptx following the theme and slide structure below. Save the .pptx next to the source PDF, named `<plan>_<client>.pptx`. Never overwrite the source or existing decks.
4. **Verify**: run `python3 scripts/check_bounds.py <deck.pptx>` — must report 0 issues. Then render previews with `python3 scripts/render_pptx.py <deck.pptx> <out_dir>` and visually inspect every slide image (Read tool). Fix and re-run until clean.
5. **Finish**: reveal the file in Finder (`open -R`), embed preview images in the reply, and note that previews are approximate (renderer uses Tahoma for everything).

## Theme (must match existing decks)

- Slide size: 10 × 5.625 in (16:9). Background: full-bleed NAVY rectangle.
- Fonts: `Calibri` for Latin/numbers; every run must also set complex-script font Tahoma via XML so Thai renders consistently. After building all slides, walk every text frame (including table cells and groups) and apply:

```python
from pptx.oxml.ns import qn
rPr = run._r.get_or_add_rPr()
cs = rPr.find(qn('a:cs'))
if cs is None:
    cs = rPr.makeelement(qn('a:cs'), {})
    rPr.append(cs)
cs.set('typeface', 'Tahoma')
```
- Colors:

| Name | Hex | Use |
|------|-----|-----|
| NAVY | 0A1F44 | slide background |
| NAVY2 | 081A38 | header/footer bars |
| NAVY3 | 13294F | panels on dark bg |
| GREEN | 16A34A | positive values, bars |
| GREEN_D | 085041 | dark green fills, emphasis text on light |
| GREEN_T | E1F5EE | green tint fills |
| GOLD | E4A22E | premium/cost accents, header underline |
| GOLD_D | 854F0B | gold text on light |
| GOLD_T | FCF3DF | gold tint fills |
| TEAL | 0D9E8A | section numbers, secondary bars |
| LIGHT | F5F7FA | zebra table rows |
| GRAY | 64748B / 94A3B8 | secondary text |
| DARK | 0F172A | body text on white |

- Header pattern (all content slides): NAVY2 bar 0.65in tall, GOLD 0.03in underline, TEAL section number ("01"…) at left, 15pt bold white title.
- Footer pattern: NAVY2 bar 0.275in at bottom with 7.5pt gray centered text: plan · quote number · agent name + phone.
- Tables: NAVY2 header row (white bold), zebra LIGHT/WHITE body, GREEN_T/GOLD_T highlight rows for milestone years, cell margins ~0.06–0.12in, middle vertical anchor, numbers right-aligned.

## Slide structure (7 slides)

1. **Title** — plan name 40pt, teal tagline, 3 lines of key facts, 4 white stat cards (total premium / total guaranteed return / net profit / yearly cashback), presenter line.
2. **vs bank deposit** — comparison table (returns, tax, yearly cash, 15-year total, life cover, tax deduction) + GREEN_D banner: "IRR การันตี ~X.XX% ปลอดภาษี ≈ ฝากประจำก่อนหักภาษี ~Y.YY% ต่อปี".
3. **Cashflow timeline** — 3 phase cards (paying years / receiving-only years / maturity) + horizontal bar timeline (GOLD premium bar, GREEN cashback bar, GREEN_D maturity block) + GOLD_T total banner.
4. **Year-by-year benefit table** — all policy years: year, age, premium, cashback, cumulative, cancel value (cumulative + CSV), death benefit. Highlight last premium year (GOLD_T) and maturity year (GREEN_T).
5. **Death benefit chart** — bar chart drawn with rectangles (TEAL growing → GREEN capped), right column of 3 NAVY3 panels with GREEN accent strip.
6. **Liquidity chart** — cancel-value bars vs GOLD reference line at total premium; panels: break-even year, value at last premium year, policy loan (~90% of CSV) option.
7. **Summary + contact** — 5 bullets, next steps (Fast track payment), GREEN_D contact card.

Default agent contact: สุภาวดี วุฒิเสน · หน่วย U2192 · ใบอนุญาต 5801115326 · โทร 096-194-5552 (confirm against the PDF; the proposal is authoritative).

## Hard rules

- Every number shown must come from the proposal PDF or be derived from it (IRR, sums). No invented figures.
- All text runs: set `font.name = "Calibri"` and the Tahoma `a:cs` element; sizes ≥ 7.5pt.
- `shadow.inherit = False` on rectangles; disable table theme banding (`bandRow=0, firstRow=0`) before setting explicit cell fills.
- Zero out textbox margins and use explicit inch geometry; keep every shape inside the canvas (verified by check_bounds.py).
- Buddhist-era dates in Thai copy (พ.ศ. = ค.ศ. + 543).
