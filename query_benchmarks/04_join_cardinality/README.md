# DuckDB join cardinality benchmark

This experiment shows that a join can change row count rather than merely attach columns. One fact table is joined to dimension tables with identical schemas but either one or five rows per key. The aggregate query returns only `COUNT(*)` and a deterministic sum involving fact and dimension fields; joined rows are never transferred to Python.

## Run

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python benchmark.py
```

Defaults are 10,000,000 fact rows and 8 threads. Use `--rows` and `--threads` to change them. At smaller validation sizes, distinct keys equal one tenth of fact rows; the final run uses 1,000,000 keys.

Each variant receives one warm-up and 10 fixed-randomized interleaved measured runs. Expected counts and sums are computed independently from source aggregates. Untimed `EXPLAIN ANALYZE` profiles record DuckDB's hash join and exposed input/output row counts.

## Measured results

The final run used 10,000,000 fact rows, 1,000,000 keys, and 8 threads.

| Matches/key | Dimension rows | Output rows | Median | Minimum | Maximum |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1,000,000 | 10,000,000 | 25.165 ms | 24.236 ms | 27.419 ms |
| 5 | 5,000,000 | 50,000,000 | 116.802 ms | 114.182 ms | 121.638 ms |

See `results.csv` and `charts/join_cardinality_runtime.png` for the complete measurements. The five-match dimension is larger and produces five times as many joined rows. Both are inherent consequences of the cardinality change, so this is not a pure measurement of output rows alone.

## Interpretation

One-to-many joins can multiply downstream work even when the query ultimately returns one aggregate row. Absolute runtimes are machine-specific; compare relative results only within this experiment.
