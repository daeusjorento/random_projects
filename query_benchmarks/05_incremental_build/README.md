# DuckDB incremental build benchmark

This experiment compares rebuilding an entire append-only target with appending one new date. The final logical target is identical in both variants.

## Run

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python benchmark.py
```

Defaults are 10,000,000 historical rows, 100,000 new rows, and 8 threads. Configure them with `--historical-rows`, `--new-rows`, and `--threads`.

The target initially contains only historical rows. Every warm-up and measured operation runs inside a transaction, verifies the final row count, date range, sums, and order-independent checksum, then rolls back. Setup, verification, and rollback are outside the timed interval; the complete `CREATE OR REPLACE TABLE` or `INSERT` write statement is timed. Ten measured variants are interleaved in a fixed randomized order after one warm-up each.

Untimed `EXPLAIN ANALYZE` profiles cover the write statements and are verified inside rolled-back transactions.

## Scope

This is an append-only example. It does not test merges, updates, deletes, late-arriving corrections, schema changes, or periodic full refreshes.

## Measured results

The final run used 10,000,000 historical rows, 100,000 new rows, and 8 threads. Both variants produced a verified 10,100,000-row target.

| Variant | Rows processed/written | Median | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Full rebuild | 10,100,000 | 88.228 ms | 87.090 ms | 91.302 ms |
| Incremental append | 100,000 | 2.386 ms | 2.284 ms | 2.506 ms |

See `results.csv` and `charts/incremental_build_runtime.png` for the complete measurements. Measured observations are separate from the interpretation below.

## Interpretation

Appending only the new date should process and write substantially fewer rows than rebuilding the complete target. Absolute runtimes depend on the machine and software environment; compare relative values only within this experiment.
