# Resolution time: statistics and outlier check

Based on 101,965 requests with a valid `resolution_hours` (out of 103,841 cleaned rows).
The other rows have no closed date, or a closed date before the created date, so they are left out.

## Summary statistics (hours)

| Measure | Value |
|---|---|
| Mean | 332.61 |
| Median | 8.20 |
| Mode (rounded to 0.1 h) | 0.4 |
| Min / Max | 0.00 / 24,242.76 |
| Range | 24,242.76 |
| Q1 / Q3 | 0.99 / 82.72 |
| IQR | 81.72 |
| Variance | 1,579,637 |
| Standard deviation | 1256.84 |
| 90th / 95th / 99th percentile | 547.6 / 1712.1 / 7148.4 |
| Skewness | 6.70 |
| Skewness after log1p | 0.74 |
| Excess kurtosis | 58.2 |
| Share over 72 h (project cut-off) | 26.8% |

## What this tells us

- The mean (333 h) is far above the median (8.2 h), so a few very long cases pull the mean up. The median is the better "typical" number, which is why the dashboard KPI uses it.
- Skewness is 6.7, strongly right-skewed. After a log transform it drops to 0.74, so the log scale is much more balanced. It is still not a single bell: the log histogram has a big peak of quick closures (under about 4 hours) and a smaller bump around 1 to 3 days, so there seem to be two kinds of cases.
- Half of the requests are closed within about 8 hours, but the 95th percentile is 1,712 hours (about 71 days).
- The mode sits near zero: many requests are closed in minutes.

## IQR outlier screening

Rule: flag values below Q1 - 1.5 x IQR or above Q3 + 1.5 x IQR.

| | Value |
|---|---|
| Lower fence | -121.59 h (negative, so no low outliers are possible) |
| Upper fence | 205.30 h (about 8.6 days) |
| High outliers | 17,001 (16.7% of valid rows) |
| Low outliers | 0 |

These are prompts to investigate, not rows to delete. A long case can be real (for example a housing repair that takes months).
Nothing was removed; the flagged rows are listed in `data/clean/resolution_outliers_2024.csv`.

### Which groups the outliers come from
Groups with fewer than 200 valid rows are left out of these tables.

**By agency**

| agency   |   rows |   outliers |   pct_of_group_that_are_outliers |   share_of_all_outliers_pct |
|:---------|-------:|-----------:|---------------------------------:|----------------------------:|
| HPD      |  21893 |       7068 |                             32.3 |                        41.6 |
| DPR      |   3767 |       2353 |                             62.5 |                        13.8 |
| DOB      |   3072 |       1696 |                             55.2 |                        10   |
| DOT      |   6007 |       1295 |                             21.6 |                         7.6 |
| DOHMH    |   2580 |        933 |                             36.2 |                         5.5 |
| DSNY     |   9175 |        904 |                              9.9 |                         5.3 |

**By complaint type**

| complaint_type       |   rows |   outliers |   pct_of_group_that_are_outliers |   share_of_all_outliers_pct |
|:---------------------|-------:|-----------:|---------------------------------:|----------------------------:|
| UNSANITARY CONDITION |   3600 |       1836 |                             51   |                        10.8 |
| PLUMBING             |   2068 |        927 |                             44.8 |                         5.5 |
| PAINT/PLASTER        |   1932 |        819 |                             42.4 |                         4.8 |
| DOOR/WINDOW          |   1379 |        769 |                             55.8 |                         4.5 |
| WATER LEAK           |   1338 |        728 |                             54.4 |                         4.3 |
| Noise - Helicopter   |    748 |        718 |                             96   |                         4.2 |

**By borough**

| borough       |   rows |   outliers |   pct_of_group_that_are_outliers |   share_of_all_outliers_pct |
|:--------------|-------:|-----------:|---------------------------------:|----------------------------:|
| BROOKLYN      |  31031 |       5203 |                             16.8 |                        30.6 |
| MANHATTAN     |  20704 |       4101 |                             19.8 |                        24.1 |
| QUEENS        |  24376 |       3565 |                             14.6 |                        21   |
| BRONX         |  22167 |       3522 |                             15.9 |                        20.7 |
| STATEN ISLAND |   3602 |        574 |                             15.9 |                         3.4 |

Read the "pct of group" column with care: it shows which groups have many long cases, but agencies handle different kinds of work, so this is not a ranking of who performs better.

## Charts
- `docs/figures/resolution_hist.png`: histogram (hidden above the 99th percentile)
- `docs/figures/resolution_hist_log.png`: histogram on a log scale
- `docs/figures/resolution_boxplot.png`: boxplot with the upper fence
- `docs/figures/resolution_boxplot_by_agency.png`: boxplot for the 8 busiest agencies
