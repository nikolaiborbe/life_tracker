#!/usr/bin/env python3
"""Daily self‑report tracker – obsession‑oriented version

Commands
--------
  python main.py morning   # AM questions → live Problems‑Solved chart
  python main.py evening   # PM questions → live Flow‑ratio chart + d6 reward outcome
  python main.py plot      # dashboard window with all numeric trends
  python main.py save      # save each metric as PNGs

Data files
----------
  morning_log.csv   evening_log.csv   *.png

Dependencies:  pip install pandas matplotlib
"""
from __future__ import annotations
import csv, sys, math, random, datetime as _dt, pathlib as _pl
import matplotlib.pyplot as _plt
import pandas as _pd

ROOT = _pl.Path(__file__).resolve().parent
LOGS = {"morning": ROOT / "morning_log.csv", "evening": ROOT / "evening_log.csv"}

# ── Helper for optional numeric input ───────────────────────────────────────

def _optional_cast(raw: str, caster):
    raw = raw.strip()
    if raw == "":
        return None
    return caster(raw)

# ── Questionnaire definitions ──────────────────────────────────────────────
MORNING_Q = [
    ("sleep_hours",   "Sleep hours last night (e.g. 7.5)? ",                         float),
    ("freshness",     "Wake freshness 1–5 (enter to skip)? ",                       int),
    ("anxiety",       "Anxiety level 1–5 (enter to skip)? ",                        int),
    ("curiosity",     "Curiosity temperature 1–5? ",                                int),
    ("motivation",    "Motivation to study 1–5? ",                                  int),
    ("prev_detox",    "Yesterday detox success 0/1 (enter skip)? ",                int),
    ("obsession_lvl", "Obsession temperature today 1–5? ",                           int),
    ("primary_goal",  "Primary technical goal for today? ",                         str),
]

EVENING_Q = [
    ("deep_work_hours",   "Hours of deep work today? ",                           float),
    ("shallow_work_hours", "Hours of shallow work today? ",                        float),
    ("problems_solved",   "Problems fully solved today (enter skip)? ",           int),
    ("progress_logged",   "Shared progress evidence today 0/1 (enter skip)? ",    int),
    ("satisfaction",      "Satisfaction with progress 1–5? ",                     int),
    ("mood",              "Evening mood 1–5? ",                                    int),
    ("biggest_insight",   "Biggest insight/lesson today: ",                        str),
]

# metric for instant pop‑up
MOTIVATION_METRIC = {"morning": "problems_solved", "evening": "total_hours"}

# ── Core functions ─────────────────────────────────────────────────────────

def _ask(period: str, qspec):
    row = {"timestamp": _dt.datetime.now().isoformat(sep=" ", timespec="seconds"),
           "period": period}

    for key, prompt, caster in qspec:
        while True:
            raw = input(prompt)
            try:
                value = _optional_cast(raw, caster) if caster is not str else raw.strip()
                row[key] = value
                break
            except ValueError:
                print("⚠️  Invalid input, try again…")

    # derived & automatic fields
    if period == "evening":
        deep = row.get("deep_work_hours") or 0
        shallow = row.get("shallow_work_hours") or 0
        total = deep + shallow
        row["flow_ratio"] = round(deep / total, 3) if total else None
        row["total_hours"] = total

        # variable‑ratio reward: roll a d6
        roll = random.randint(1, 6)
        row["die_roll"] = roll
        row["reward"] = 1 if roll == 1 else 0
        print(f"🎲  You rolled a {roll}. {'Reward! 🎉' if roll == 1 else 'No reward today.'}")

    _write(period, row)
    print("✅ Logged", period)

    metric = MOTIVATION_METRIC.get(period)
    if metric == "flow_ratio":
        print("""Flow ratio = deep_work_hours / (deep_work_hours + shallow_work_hours).
              Higher means a greater share of your day was true, distraction‑free deep work.""")
    if metric:
        _plot_single(metric, display=True, save=False,
                     title_suffix=f" — {period.capitalize()}")


def _write(period: str, row: dict):
    path = LOGS[period]

    # If the file exists, load existing rows so we can harmonize columns
    if path.exists():
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            rows   = list(reader)
            existing_fields = reader.fieldnames or []
    else:
        rows, existing_fields = [], []

    # Union of previous columns and any new keys in this row (order preserved)
    fieldnames = list(dict.fromkeys(existing_fields + list(row.keys())))

    # Append today’s row to list
    rows.append(row)

    # Rewrite whole CSV with updated header so every line matches field count
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            # Ensure every dict has every key (empty string for missing)
            writer.writerow({k: r.get(k, "") for k in fieldnames})

# ── Data & plotting helpers ────────────────────────────────────────────────

def _load_all() -> _pd.DataFrame:
    dfs = [_pd.read_csv(p, parse_dates=["timestamp"]) for p in LOGS.values() if p.exists()]
    return _pd.concat(dfs, ignore_index=True) if dfs else _pd.DataFrame()


def _plot_all(display: bool, save: bool):
    df = _load_all()
    if df.empty:
        print("No log data yet.")
        return

    numeric = df.select_dtypes(include=["int64", "float64"])
    if numeric.empty:
        print("No numeric fields yet.")
        return

    cols = numeric.columns.tolist()
    if display:
        _show_grid(df, cols)
    if save:
        for col in cols:
            _plot_single(col, df=df, display=False, save=True)


def _show_grid(df: _pd.DataFrame, cols: list[str]):
    import matplotlib.pyplot as plt
    n = len(cols)
    ncols = 2 if n > 1 else 1
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4 * nrows), squeeze=False)
    df_sorted = df.sort_values("timestamp")
    for i, col in enumerate(cols):
        ax = axes[i // ncols][i % ncols]
        ax.plot(df_sorted["timestamp"], df_sorted[col], marker="o")
        ax.set_title(col.replace("_", " ").title())
        ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    plt.show()


def _plot_single(col: str, *, df: _pd.DataFrame | None = None, display: bool, save: bool, title_suffix: str = ""):
    if df is None:
        df = _load_all()
    if col not in df.columns:
        return

    df_sorted = df.sort_values("timestamp")
    y = df_sorted[col].fillna(0)

    # Cumulative view for problems_solved
    if col == "problems_solved":
        y = y.cumsum()
        label = "Cumulative Problems Solved"
    elif col == "total_hours":
        y = y.cumsum()
        label = "Cumulative Total Hours Worked"
    else:
        label = col.replace("_", " ").title()

    _plt.figure()
    _plt.plot(df_sorted["timestamp"], y, marker="o")
    _plt.title(label + title_suffix)
    _plt.xlabel("Date")
    _plt.tight_layout()
    if save:
        out = ROOT / f"{col}.png"
        _plt.savefig(out, dpi=150)
        print("📈 Saved", out.name)
    if display:
        _plt.show()
    else:
        _plt.close()

# ── Entry point ────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "morning":
        _ask("morning", MORNING_Q)
    elif cmd == "evening":
        _ask("evening", EVENING_Q)
    elif cmd == "plot":
        _plot_all(display=True, save=False)
    elif cmd == "save":
        _plot_all(display=False, save=True)
    else:
        print("Unknown command:", cmd)
        sys.exit(1)

if __name__ == "__main__":
    main()


