"""
Build maps/generations.json from the autoevolution schema
(../car-schemas/cars_dataset.json).

For every make/model we produce a clean, NON-OVERLAPPING list of generation
year-ranges at facelift granularity:

    "Toyota": {
        "Camry": [
            {"range": "2011-2014", "start": 2011, "end": 2014, "name": "..."},
            {"range": "2015-2017", "start": 2015, "end": 2017, "name": "..."},
            ...
        ]
    }

Autoevolution data is very granular: it splits a model into body-style / regional
variants ("Corolla Sedan", "Corolla 3 Doors", "Corolla (US)") and lists overlapping
generations. Listing sites (TrueCar) use a single model name ("Corolla"), so we:

  1. Aggregate body-style / regional variants into one BASE model
     ("Corolla Sedan" + "Corolla 3 Doors" -> "Corolla"), while keeping genuinely
     distinct models ("Corolla Cross", "Corolla Verso") separate.
  2. Collect every generation start year across the aggregated variants and build a
     sequential, non-overlapping timeline so each calendar year maps to exactly one
     generation.
"""
import json
import re
import os
from pathlib import Path
from collections import defaultdict

CURRENT_YEAR = 2026

# Default location of the autoevolution dataset (sibling project under Projects/).
DEFAULT_SOURCE = Path(__file__).resolve().parents[3] / "car-schemas" / "cars_dataset.json"
OUTPUT_PATH = Path("maps") / "generations.json"

# Body-style / regional qualifiers that do NOT define a different model on a
# listing site. Stripping these collapses variants onto their base model name.
BODY_QUALIFIERS = {
    "sedan", "saloon", "wagon", "estate", "touring", "liftback", "hatchback",
    "hatch", "coupe", "convertible", "cabrio", "cabriolet", "3 doors", "5 doors",
    "3-door", "5-door", "3door", "5door", "doors", "door",
}
# Regional qualifiers in parentheses, e.g. "Corolla (US)", "Camry (EU)".
REGION_PAT = re.compile(r"\((?:u\.?s\.?a?|eu|jdm|uk|cn|china|europe|us)\)", re.IGNORECASE)

YEARS_PAT = re.compile(r"(\d{4})\s*-\s*(\d{4}|present)", re.IGNORECASE)

# Makes whose names should stay upper-cased rather than title-cased.
ACRONYM_MAKES = {
    "BMW", "BYD", "GMC", "AC", "DS", "MG", "RAM", "KTM", "MINI", "SEAT", "BAIC",
    "GAC", "FAW", "SAIC", "VAZ", "ARO", "DR", "MV",
}


def canon_make(name: str) -> str:
    name = name.strip()
    if name.upper() in ACRONYM_MAKES:
        return name.upper()
    # Title-case each word but keep short all-caps tokens (e.g. "ALFA ROMEO").
    return " ".join(w.capitalize() for w in name.split())


def base_model(model: str) -> str:
    """Reduce an autoevolution model name to its listing-site base name."""
    m = REGION_PAT.sub("", model).strip()
    # Drop trailing body-style qualifiers, but never reduce to an empty string.
    tokens = m.split()
    while len(tokens) > 1:
        # Check the last 1-2 tokens against the qualifier set.
        last1 = tokens[-1].lower()
        last2 = " ".join(tokens[-2:]).lower()
        if last2 in BODY_QUALIFIERS:
            tokens = tokens[:-2]
        elif last1 in BODY_QUALIFIERS:
            tokens = tokens[:-1]
        else:
            break
    return " ".join(tokens).strip()


def parse_years(years: str):
    """'2013 - 2016' -> (2013, 2016); '2020 - Present' -> (2020, CURRENT_YEAR)."""
    mt = YEARS_PAT.search(years or "")
    if not mt:
        return None
    start = int(mt.group(1))
    end_raw = mt.group(2)
    end = CURRENT_YEAR if end_raw.lower() == "present" else int(end_raw)
    if end < start:
        end = start
    return start, end


def build_timeline(entries, min_gap=3):
    """
    entries: list of (start, end, name) for one base model (across variants).
    Returns a sequential, non-overlapping list of generation dicts.

    Autoevolution lists many overlapping intervals for a single model because of
    regional re-releases and derivative variants (e.g. a hybrid or a TRD trim that
    debuts mid-generation). Those create spurious 1-2 year "generations". We keep
    facelift-level splits (typically >= 3-4 years apart) but absorb shorter slivers
    by greedily choosing generation start years that are at least `min_gap` apart.
    """
    by_start = {}  # start year -> (own_end, representative name)
    for start, end, name in entries:
        if start not in by_start or end < by_start[start][0]:
            by_start[start] = (end, name)

    starts = sorted(by_start)
    if not starts:
        return []

    # Greedily pick breakpoints at least `min_gap` years apart.
    chosen = []
    last = None
    for s in starts:
        if last is None or s - last >= min_gap:
            chosen.append(s)
            last = s

    overall_end = max(e for _, e, _ in entries)

    gens = []
    for i, s in enumerate(chosen):
        _, name = by_start[s]
        if i + 1 < len(chosen):
            end = chosen[i + 1] - 1
        else:
            end = max(overall_end, s)
        if end < s:
            end = s
        gens.append({
            "range": f"{s}-{end}",
            "start": s,
            "end": end,
            "name": name,
        })
    return gens


def populate(source=DEFAULT_SOURCE, output=OUTPUT_PATH):
    source = Path(source)
    if not source.exists():
        print(f"Source dataset not found: {source}")
        return

    with open(source, "r", encoding="utf-8") as f:
        ae = json.load(f)

    result = {}
    total_models = 0
    total_gens = 0

    for brand, models in ae.items():
        make = canon_make(brand)
        # Aggregate variant generations by base model name.
        agg = defaultdict(list)
        for model_name, mdata in models.items():
            bm = base_model(model_name)
            if not bm:
                continue
            for g in mdata.get("generations", []):
                pr = parse_years(g.get("years", ""))
                if pr:
                    agg[bm].append((pr[0], pr[1], g.get("name", "")))

        make_out = {}
        for bm, entries in agg.items():
            if not entries:
                continue
            gens = build_timeline(entries)
            if gens:
                make_out[bm] = gens
                total_models += 1
                total_gens += len(gens)

        if make_out:
            result[make] = make_out

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Wrote {output}")
    print(f"  Makes:       {len(result)}")
    print(f"  Models:      {total_models}")
    print(f"  Generations: {total_gens}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    ap.add_argument("--output", default=str(OUTPUT_PATH))
    populate(**vars(ap.parse_args()))
