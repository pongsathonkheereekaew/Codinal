# Harness eval

`cases/market-bench.json` defines reproducible benchmark cases consumed by
`scripts/bench/run-bench.sh`. Each case is a small fixture repo with a passing
baseline test.

Fixture contract:

```bash
python3 -c "import json; d=json.load(open('harness/eval/cases/market-bench.json')); assert len(d['cases'])==3"
```

Runner:

```bash
bash scripts/bench/run-bench.sh
```
