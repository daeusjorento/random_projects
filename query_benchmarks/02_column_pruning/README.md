# DuckDB column pruning benchmark

This experiment measures how selecting more Parquet columns affects DuckDB query performance while holding row count, data types, storage format, hardware, thread count, and returned row count constant.

The benchmark generates one local Parquet file with an `id` column and 25 deterministic `INTEGER` measurement columns named `value_01` through `value_25`. The three queries read and aggregate 1, 5, or 25 measurement columns from that same file. Every query returns exactly one row with one `SUM()` result per selected column. It does not use `COUNT(*)`, which Parquet metadata may answer without reading column data.

All core comparison columns are identical integer types. Mixing strings, booleans, and integers would confound column count with data type and aggregation cost, so mixed data types are reserved for a later experiment.

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

The generated Parquet file is stored under `data/` and is ignored by Git. Each invocation replaces that generated file.

## Procedure

Each query receives one unmeasured warm-up. The benchmark then performs 10 measured executions per query, interleaving the three variants in a fixed randomized order. Every execution is checked against deterministic expected aggregate values. `EXPLAIN ANALYZE` runs separately from timing and writes one profile per query under `profiles/`; the script verifies that each profile projects only the requested Parquet columns.

## Measured results

The final run used 10,000,000 rows, 8 DuckDB threads, and a 40,485,901-byte (38.61 MiB) Parquet file. Each result summarizes 10 measured executions after one warm-up.

| Columns read | Median | Minimum | Maximum |
| ---: | ---: | ---: | ---: |
| 1 | 4.502 ms | 4.186 ms | 5.076 ms |
| 5 | 15.938 ms | 15.208 ms | 17.895 ms |
| 25 | 73.920 ms | 72.605 ms | 103.702 ms |

The complete recorded measurements are in `results.csv`, and `charts/column_pruning_runtime.png` plots median runtime against columns read. These are machine-specific observations, not universal performance guarantees.

## Interpretation

Reading and aggregating more columns generally requires DuckDB to decode and process more Parquet column data. The relative differences within one run are more useful than comparing absolute milliseconds across machines, because CPU load, memory bandwidth, filesystem caching, DuckDB version, and hardware all affect elapsed time.
