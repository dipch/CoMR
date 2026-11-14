#!/usr/bin/env python3
"""Per-step and per-phase timing report for one CoMR run.

Combines two sources Snakemake writes anyway:
  * benchmarks_<FASTA>/<Rule>.tsv  -> wall time, CPU time, peak memory per rule
  * .snakemake/log/*.snakemake.log -> start / finish timestamp per job

Writes timing_steps.tsv and timing_phases.tsv to --out-dir and prints both.
Standard library only.

Usage:
  python utils/timing_report.py --bench-dir OUT/benchmarks_pilot_100 \
      --snakemake-log OUT/snakemake_run.log --out-dir OUT
"""
import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

PHASES = {
    "1_qc_data_processing": ["Fasta_format", "Metstart"],
    "2_targeting_prediction": ["Targetp", "Mitofates", "Mitoprot", "Deepmito"],
    "3_homology_search": ["HMMscan", "SubtractiveDB_blastp", "CustomDB_blastp", "NR_blastp"],
    "4_parsing": ["HMM_parse", "SubtractiveDB_parse", "CustomDB_parse", "NR_parse", "Trees_parse"],
    "5_alignment_trees": ["HMM_align", "HMM_trees"],
    "6_scoring": ["Results", "CoMR_scores"],
}
RULE_TO_PHASE = {r: p for p, rules in PHASES.items() for r in rules}

TS_RE = re.compile(r"^\[(\w{3} \w{3}\s+\d+ \d\d:\d\d:\d\d \d{4})\]$")
RULE_RE = re.compile(r"^(?:local)?rule (\w+):$")
JOBID_RE = re.compile(r"^\s+jobid: (\d+)$")
FINISHED_RE = re.compile(r"^Finished job (\d+)\.$")
ERROR_RE = re.compile(r"^Error in rule (\w+):$")


def hms(seconds):
    if seconds is None:
        return "NA"
    s = int(round(seconds))
    return f"{s // 3600:02d}h:{s % 3600 // 60:02d}m:{s % 60:02d}s"


def fmt(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "NA"


def parse_snakemake_log(path):
    """Return {rule: {"start": dt, "end": dt, "status": str}} from a Snakemake 7 log."""
    jobs, steps = {}, {}
    last_ts, pending_rule = None, None
    if not path or not Path(path).is_file():
        return steps
    for line in Path(path).read_text(errors="replace").splitlines():
        if m := TS_RE.match(line):
            last_ts = datetime.strptime(m.group(1), "%a %b %d %H:%M:%S %Y")
        elif m := RULE_RE.match(line):
            pending_rule = m.group(1)
        elif (m := JOBID_RE.match(line)) and pending_rule:
            jobs[m.group(1)] = pending_rule
            steps[pending_rule] = {"start": last_ts, "end": None, "status": "started"}
            pending_rule = None
        elif m := FINISHED_RE.match(line):
            rule = jobs.get(m.group(1))
            if rule:
                steps[rule].update(end=last_ts, status="done")
        elif m := ERROR_RE.match(line):
            steps.setdefault(m.group(1), {"start": None})
            steps[m.group(1)].update(end=last_ts, status="FAILED")
    steps.pop("all", None)
    return steps


def read_benchmarks(bench_dir):
    """Return {rule: {"s": float, "cpu_time": float, "max_rss": float}}."""
    out = {}
    for tsv in sorted(Path(bench_dir).glob("*.tsv")):
        with tsv.open() as fh:
            row = next(csv.DictReader(fh, delimiter="\t"), None)
        if not row:
            continue

        def num(key):
            try:
                return float(row.get(key, "NA"))
            except ValueError:
                return None

        out[tsv.stem] = {"s": num("s"), "cpu_time": num("cpu_time"), "max_rss": num("max_rss")}
    return out


def phase_order(rule):
    phase = RULE_TO_PHASE.get(rule, "9_other")
    return (phase, rule)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench-dir", required=True)
    ap.add_argument("--snakemake-log", default=None)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    log_steps = parse_snakemake_log(args.snakemake_log)
    bench = read_benchmarks(args.bench_dir)
    rules = sorted(set(log_steps) | set(bench), key=phase_order)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- per step ----
    step_rows = []
    for rule in rules:
        lg, bm = log_steps.get(rule, {}), bench.get(rule, {})
        step_rows.append({
            "phase": RULE_TO_PHASE.get(rule, "9_other"),
            "rule": rule,
            "status": lg.get("status", "done" if bm else "NA"),
            "start": fmt(lg.get("start")),
            "end": fmt(lg.get("end")),
            "wall_s": f"{bm['s']:.1f}" if bm.get("s") is not None else "NA",
            "wall_hms": hms(bm.get("s")),
            "cpu_s": f"{bm['cpu_time']:.1f}" if bm.get("cpu_time") is not None else "NA",
            "max_rss_mb": f"{bm['max_rss']:.0f}" if bm.get("max_rss") is not None else "NA",
        })

    # ---- per phase ----
    # elapsed = first start -> last end (what you waited; steps overlap)
    # summed  = sum of step wall times (how much work the tools did)
    phase_rows = []
    for phase in sorted({r["phase"] for r in step_rows}):
        members = [r for r in rules if RULE_TO_PHASE.get(r, "9_other") == phase]
        starts = [log_steps[r]["start"] for r in members if log_steps.get(r, {}).get("start")]
        ends = [log_steps[r]["end"] for r in members if log_steps.get(r, {}).get("end")]
        walls = [bench[r]["s"] for r in members if bench.get(r, {}).get("s") is not None]
        rss = [bench[r]["max_rss"] for r in members if bench.get(r, {}).get("max_rss") is not None]
        elapsed = (max(ends) - min(starts)).total_seconds() if starts and ends else None
        phase_rows.append({
            "phase": phase,
            "rules": ",".join(members),
            "start": fmt(min(starts) if starts else None),
            "end": fmt(max(ends) if ends else None),
            "elapsed_hms": hms(elapsed),
            "summed_step_hms": hms(sum(walls) if walls else None),
            "peak_rss_mb": f"{max(rss):.0f}" if rss else "NA",
        })

    all_starts = [v["start"] for v in log_steps.values() if v.get("start")]
    all_ends = [v["end"] for v in log_steps.values() if v.get("end")]
    if all_starts and all_ends:
        phase_rows.append({
            "phase": "TOTAL_workflow",
            "rules": f"{len(rules)} rules",
            "start": fmt(min(all_starts)),
            "end": fmt(max(all_ends)),
            "elapsed_hms": hms((max(all_ends) - min(all_starts)).total_seconds()),
            "summed_step_hms": hms(sum(v["s"] for v in bench.values() if v.get("s") is not None)),
            "peak_rss_mb": "",
        })

    for name, rows in (("timing_steps.tsv", step_rows), ("timing_phases.tsv", phase_rows)):
        if not rows:
            print(f"no data for {name}")
            continue
        path = out_dir / name
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t")
            w.writeheader()
            w.writerows(rows)
        print(f"\n== {path}")
        cols = list(rows[0])
        widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
        print("  ".join(c.ljust(widths[c]) for c in cols))
        for r in rows:
            print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))


if __name__ == "__main__":
    main()
