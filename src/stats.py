import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean" / "nyc311_clean_2024.csv"
FIG_DIR = ROOT / "docs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(CLEAN, usecols=["unique_key", "agency", "complaint_type", "borough", "resolution_hours"])
total_rows = len(df)
res = df["resolution_hours"].dropna()
n = len(res)

q1, q3 = res.quantile(0.25), res.quantile(0.75)
iqr = q3 - q1
mode = res.round(1).mode().iloc[0]

summary = {
    "n_valid": n,
    "n_rows_total": total_rows,
    "mean": res.mean(),
    "median": res.median(),
    "mode_rounded_0.1h": mode,
    "min": res.min(),
    "max": res.max(),
    "range": res.max() - res.min(),
    "q1": q1,
    "q3": q3,
    "iqr": iqr,
    "variance": res.var(),
    "std": res.std(),
    "p90": res.quantile(0.90),
    "p95": res.quantile(0.95),
    "p99": res.quantile(0.99),
    "skewness": stats.skew(res),
    "excess_kurtosis": stats.kurtosis(res),
    "share_over_72h": (res > 72).mean(),
}

log_res = np.log1p(res)
summary["skewness_log1p"] = stats.skew(log_res)

low_fence = q1 - 1.5 * iqr
high_fence = q3 + 1.5 * iqr
is_high = res > high_fence
is_low = res < low_fence
summary.update({
    "low_fence": low_fence,
    "high_fence": high_fence,
    "n_outliers_high": int(is_high.sum()),
    "n_outliers_low": int(is_low.sum()),
    "pct_outliers": (is_high.sum() + is_low.sum()) / n,
})

valid = df.dropna(subset=["resolution_hours"]).copy()
valid["outlier"] = (valid["resolution_hours"] > high_fence) | (valid["resolution_hours"] < low_fence)


def outlier_table(col, top=6):
    t = valid.groupby(col).agg(rows=("outlier", "size"), outliers=("outlier", "sum"))
    t["pct_of_group_that_are_outliers"] = (t["outliers"] / t["rows"] * 100).round(1)
    t["share_of_all_outliers_pct"] = (t["outliers"] / t["outliers"].sum() * 100).round(1)
    return t[t["rows"] >= 200].sort_values("outliers", ascending=False).head(top)


by_agency = outlier_table("agency")
by_complaint = outlier_table("complaint_type")
by_borough = outlier_table("borough")

flagged = valid.loc[valid["outlier"], ["unique_key", "agency", "complaint_type", "resolution_hours"]]
flagged.sort_values("resolution_hours", ascending=False).to_csv(
    ROOT / "data" / "clean" / "resolution_outliers_2024.csv", index=False)

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.hist(res[res <= summary["p99"]], bins=60, color="#4c78a8", edgecolor="white")
ax.axvline(summary["median"], color="#e45756", linestyle="--", label=f"median {summary['median']:.1f} h")
ax.axvline(summary["mean"], color="#f58518", linestyle="--", label=f"mean {summary['mean']:.1f} h")
ax.set_xlabel("resolution time (hours), values above the 99th percentile hidden")
ax.set_ylabel("requests")
ax.set_title("Resolution time is strongly right-skewed")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "resolution_hist.png", dpi=150)
plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.hist(log_res, bins=60, color="#54a24b", edgecolor="white")
ticks = [0, 1, 4, 24, 72, 168, 720, 8760]
ax.set_xticks(np.log1p(ticks))
ax.set_xticklabels([str(t) for t in ticks])
ax.set_xlabel("resolution time (hours), log scale")
ax.set_ylabel("requests")
ax.set_title("Resolution time after log transform")
fig.tight_layout()
fig.savefig(FIG_DIR / "resolution_hist_log.png", dpi=150)
plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 3.5))
ax.boxplot(res + 0.01, orientation="horizontal", whis=1.5, flierprops={"markersize": 2, "alpha": 0.3})
ax.set_xscale("log")
ax.axvline(high_fence, color="#e45756", linestyle=":", label=f"upper fence {high_fence:.0f} h")
ax.set_xlabel("resolution time (hours), log axis")
ax.set_yticks([])
ax.set_title("Boxplot of resolution time")
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "resolution_boxplot.png", dpi=150)
plt.close(fig)

top_agencies = valid["agency"].value_counts().head(8).index
fig, ax = plt.subplots(figsize=(8, 4.5))
data = [valid.loc[valid["agency"] == a, "resolution_hours"] + 0.01 for a in top_agencies]
ax.boxplot(data, tick_labels=list(top_agencies), whis=1.5, flierprops={"markersize": 2, "alpha": 0.3})
ax.set_yscale("log")
ax.set_ylabel("resolution time (hours), log axis")
ax.set_title("Resolution time by agency (8 busiest)")
fig.tight_layout()
fig.savefig(FIG_DIR / "resolution_boxplot_by_agency.png", dpi=150)
plt.close(fig)

clean_summary = {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else int(v)) for k, v in summary.items()}
(ROOT / "docs" / "stats_summary.json").write_text(json.dumps(clean_summary, indent=2))

s = summary
md = f"""# Resolution time: statistics and outlier check

Based on {n:,} requests with a valid `resolution_hours` (out of {total_rows:,} cleaned rows).
The other rows have no closed date, or a closed date before the created date, so they are left out.

## Summary statistics (hours)

| Measure | Value |
|---|---|
| Mean | {s['mean']:.2f} |
| Median | {s['median']:.2f} |
| Mode (rounded to 0.1 h) | {s['mode_rounded_0.1h']:.1f} |
| Min / Max | {s['min']:.2f} / {s['max']:,.2f} |
| Range | {s['range']:,.2f} |
| Q1 / Q3 | {s['q1']:.2f} / {s['q3']:.2f} |
| IQR | {s['iqr']:.2f} |
| Variance | {s['variance']:,.0f} |
| Standard deviation | {s['std']:.2f} |
| 90th / 95th / 99th percentile | {s['p90']:.1f} / {s['p95']:.1f} / {s['p99']:.1f} |
| Skewness | {s['skewness']:.2f} |
| Skewness after log1p | {s['skewness_log1p']:.2f} |
| Excess kurtosis | {s['excess_kurtosis']:.1f} |
| Share over 72 h (project cut-off) | {s['share_over_72h']:.1%} |

## What this tells us

- The mean ({s['mean']:.0f} h) is far above the median ({s['median']:.1f} h), so a few very long cases pull the mean up. The median is the better "typical" number, which is why the dashboard KPI uses it.
- Skewness is {s['skewness']:.1f}, strongly right-skewed. After a log transform it drops to {s['skewness_log1p']:.2f}, so the log scale is much more balanced. It is still not a single bell: the log histogram has a big peak of quick closures (under about 4 hours) and a smaller bump around 1 to 3 days, so there seem to be two kinds of cases.
- Half of the requests are closed within about {s['median']:.0f} hours, but the 95th percentile is {s['p95']:,.0f} hours (about {s['p95'] / 24:.0f} days).
- The mode sits near zero: many requests are closed in minutes.

## IQR outlier screening

Rule: flag values below Q1 - 1.5 x IQR or above Q3 + 1.5 x IQR.

| | Value |
|---|---|
| Lower fence | {low_fence:.2f} h (negative, so no low outliers are possible) |
| Upper fence | {high_fence:.2f} h (about {high_fence / 24:.1f} days) |
| High outliers | {s['n_outliers_high']:,} ({s['pct_outliers']:.1%} of valid rows) |
| Low outliers | {s['n_outliers_low']:,} |

These are prompts to investigate, not rows to delete. A long case can be real (for example a housing repair that takes months).
Nothing was removed; the flagged rows are listed in `data/clean/resolution_outliers_2024.csv`.

### Which groups the outliers come from
Groups with fewer than 200 valid rows are left out of these tables.

**By agency**

{by_agency.to_markdown()}

**By complaint type**

{by_complaint.to_markdown()}

**By borough**

{by_borough.to_markdown()}

Read the "pct of group" column with care: it shows which groups have many long cases, but agencies handle different kinds of work, so this is not a ranking of who performs better.

## Charts
- `docs/figures/resolution_hist.png`: histogram (hidden above the 99th percentile)
- `docs/figures/resolution_hist_log.png`: histogram on a log scale
- `docs/figures/resolution_boxplot.png`: boxplot with the upper fence
- `docs/figures/resolution_boxplot_by_agency.png`: boxplot for the 8 busiest agencies
"""
(ROOT / "docs" / "stats_report.md").write_text(md)

print(f"valid rows: {n:,}")
print(f"mean {s['mean']:.1f} h | median {s['median']:.1f} h | skew {s['skewness']:.1f} (log1p {s['skewness_log1p']:.2f})")
print(f"fences: {low_fence:.1f} .. {high_fence:.1f} h | high outliers: {s['n_outliers_high']:,} ({s['pct_outliers']:.1%})")
