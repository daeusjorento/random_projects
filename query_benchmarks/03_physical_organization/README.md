# Parquet physical organization benchmark

This experiment measures how the physical ordering of identical data affects Parquet row-group eligibility and DuckDB query runtime.

The script generates two local Parquet files with the same deterministic rows and columns: `sorted_by_date.parquet` is ordered by `event_date`, while `random_order.parquet` is ordered by `hash(id)`. Both use ZSTD compression and 122,880-row groups. No dataset is downloaded, and generated files under `data/` are ignored by Git.

The query filters the same seven-day interval from 2025-06-15 through 2025-06-21 and returns one row containing `COUNT(*)` and `SUM(value)`. The full generated date range contains 365 possible dates beginning on 2025-01-01.

## Run it

Python 3.9 or newer is recommended.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python benchmark.py
```

The defaults are 10,000,000 rows and 8 DuckDB threads. Both are configurable:

```sh
python benchmark.py --rows 1000000 --threads 8
```

## Procedure and verification

Each file receives one unmeasured warm-up followed by 10 measured executions, interleaved in a fixed randomized order. The script verifies that both files have the same total row count, minimum and maximum date, aggregate sums, order-independent hash checksum, and filtered result.

`row_group_stats.csv` contains the `event_date` minimum and maximum from DuckDB's `parquet_metadata()` function for every row group. An overlapping row group is one whose statistics make it eligible to be scanned for the date filter. This experiment does not claim an exact number of row groups skipped unless DuckDB exposes that directly. Untimed `EXPLAIN ANALYZE` output is stored under `profiles/`.

## Measured results

The final run used 10,000,000 input rows, 8 DuckDB threads, and found 191,779 matching rows. Each result summarizes 10 measured executions after one warm-up.

| Physical organization | Eligible row groups | Median | Minimum | Maximum | File size |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sorted by date | 3 of 82 | 1.218 ms | 1.084 ms | 1.327 ms | 49,281,728 bytes |
| Random order | 82 of 82 | 6.825 ms | 6.596 ms | 7.893 ms | 98,537,392 bytes |

The complete measurements are recorded in `results.csv`, and `charts/physical_organization_runtime.png` compares median runtime. The two file sizes differ because sorting affected compression as well as row-group statistics.

## Interpretation

When dates are physically clustered, a narrow date filter should overlap fewer row groups than it does in randomly ordered data. This can reduce the amount of Parquet data eligible for scanning. Absolute runtimes depend on hardware, filesystem caching, system load, and software versions; relative results from the same run are more informative.
