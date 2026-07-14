#!/usr/bin/env python3
"""Validate Easby structured JSON output. PASS -> exit 0; FAIL -> exit 1."""
from __future__ import annotations
import json
import sys
from typing import Optional

VALID_OPS = {
    "sequence", "inversion", "deceptive_cadence", "secondary_dominant",
    "mode_mixture", "picardy", "borrowed_bVII", "borrowed_bVI",
    "sequential_lift", "passing_tone",
}

VALID_WAVEFORMS = {"sawtooth", "square", "sine", "triangle", "noise", "pulse", "fm", "additive"}
VALID_VCF_TYPES = {"lpf", "hpf", "bpf"}
VALID_VCF_CUTOFF = {"closed", "half", "open"}
VALID_SLOPES = {6, 12, 24}
VALID_ADSR_TIME = {"fast", "med", "slow", "short", "long"}


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def load(src: Optional[str]) -> dict:
    try:
        raw = open(src).read() if src else sys.stdin.read()
    except FileNotFoundError:
        fail(f"file not found: {src!r}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"invalid JSON: {e}")


def validate_variation(d: dict) -> None:
    amt = d.get("amt")
    if not isinstance(amt, int) or not 1 <= amt <= 5:
        fail(f"amt must be 1..5, got {amt!r}")

    op = d.get("operation")
    if op not in VALID_OPS:
        fail(f"operation {op!r} not in {sorted(VALID_OPS)}")

    confidence = d.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
        fail(f"confidence must be float 0..1, got {confidence!r}")

    if op in {"passing_tone", "inversion"} and confidence < 0.7:
        fail(f"operation {op!r} requires confidence >= 0.7, got {confidence}")

    ops = d.get("slice_ops")
    if not isinstance(ops, list) or not ops:
        fail("slice_ops must be a non-empty list")

    for i, s in enumerate(ops):
        sd = s.get("semitone_delta")
        ts = s.get("time_stretch")
        if not isinstance(sd, (int, float)) or not -12 <= sd <= 12:
            fail(f"slice_ops[{i}].semitone_delta must be -12..+12, got {sd!r}")
        if not isinstance(ts, (int, float)) or not 0.5 <= ts <= 2.0:
            fail(f"slice_ops[{i}].time_stretch must be 0.5..2.0, got {ts!r}")
        if op == "passing_tone" and abs(sd) > 4:
            fail(f"passing_tone slice_ops[{i}] |semitone_delta|={abs(sd)} > 4 (M3 gap rule)")

    for field in ("expected_audible_change", "theory_basis"):
        val = d.get(field)
        if not isinstance(val, str) or not val.strip():
            fail(f"{field!r} must be a non-empty string, got {val!r}")


def validate_sound_design(d: dict) -> None:
    waveform = d.get("waveform")
    if waveform not in VALID_WAVEFORMS:
        fail(f"waveform {waveform!r} not in {sorted(VALID_WAVEFORMS)}")

    vcf = d.get("vcf")
    if not isinstance(vcf, dict):
        fail("vcf must be an object")
    if vcf.get("type") not in VALID_VCF_TYPES:
        fail(f"vcf.type {vcf.get('type')!r} not in {sorted(VALID_VCF_TYPES)}")
    if vcf.get("cutoff_relative") not in VALID_VCF_CUTOFF:
        fail(f"vcf.cutoff_relative {vcf.get('cutoff_relative')!r} not in {sorted(VALID_VCF_CUTOFF)}")
    if vcf.get("slope_db_oct") not in VALID_SLOPES:
        fail(f"vcf.slope_db_oct must be 6, 12, or 24, got {vcf.get('slope_db_oct')!r}")
    res = vcf.get("resonance")
    if not isinstance(res, (int, float)) or not 0.0 <= res <= 1.0:
        fail(f"vcf.resonance must be float 0..1, got {res!r}")

    for adsr_key in ("adsr_vca", "adsr_vcf"):
        adsr = d.get(adsr_key)
        if not isinstance(adsr, dict):
            fail(f"{adsr_key} must be an object")
        sus = adsr.get("sustain")
        if not isinstance(sus, (int, float)) or not 0.0 <= sus <= 1.0:
            fail(f"{adsr_key}.sustain must be float 0..1, got {sus!r}")
        for t in ("attack", "decay", "release"):
            val = adsr.get(t)
            if val not in VALID_ADSR_TIME:
                fail(f"{adsr_key}.{t} {val!r} not in {sorted(VALID_ADSR_TIME)}")

    if waveform == "fm":
        fm = d.get("fm_params")
        if not isinstance(fm, dict):
            fail("fm_params required when waveform == 'fm'")
        for k in ("C_ratio", "M_ratio", "I_start", "I_end"):
            if not isinstance(fm.get(k), (int, float)):
                fail(f"fm_params.{k} must be numeric, got {fm.get(k)!r}")


def validate(d: dict) -> None:
    t = d.get("type")
    if t == "VariationDecision":
        validate_variation(d)
    elif t == "SoundDesignTarget":
        validate_sound_design(d)
    else:
        fail(f"type must be 'VariationDecision' or 'SoundDesignTarget', got {t!r}")
    print("PASS")


if __name__ == "__main__":
    validate(load(sys.argv[1] if len(sys.argv) > 1 else None))
