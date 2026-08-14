# Query benchmark results

These tables summarize the committed `results.csv` files. Relative runtime uses the fastest variant within each experiment as `1.00×`; it should never be compared across experiments.

| Experiment | Comparison | Median runtime | Relative runtime | Important supporting measure | GitHub |
| --- | --- | ---: | ---: | --- | --- |
| 01 Row count | 100,000 rows | 0.176 ms | 1.00× | Verified sum: 49,950,000 | [Experiment 01](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/01_row_count) |
| 01 Row count | 1,000,000 rows | 0.431 ms | 2.45× | Verified sum: 499,500,000 | [Experiment 01](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/01_row_count) |
| 01 Row count | 10,000,000 rows | 2.494 ms | 14.17× | Verified sum: 4,995,000,000 | [Experiment 01](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/01_row_count) |
| 02 Column pruning | 1 integer column | 4.502 ms | 1.00× | 10,000,000 input rows | [Experiment 02](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/02_column_pruning) |
| 02 Column pruning | 5 integer columns | 15.938 ms | 3.54× | 10,000,000 input rows | [Experiment 02](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/02_column_pruning) |
| 02 Column pruning | 25 integer columns | 73.920 ms | 16.42× | 10,000,000 input rows | [Experiment 02](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/02_column_pruning) |
| 03 Physical organization | Sorted by date | 1.218 ms | 1.00× | 3 of 82 row groups eligible | [Experiment 03](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/03_physical_organization) |
| 03 Physical organization | Random order | 6.825 ms | 5.60× | 82 of 82 row groups eligible | [Experiment 03](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/03_physical_organization) |
| 04 Join cardinality | 1 match per key | 25.165 ms | 1.00× | 10,000,000 output rows | [Experiment 04](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/04_join_cardinality) |
| 04 Join cardinality | 5 matches per key | 116.802 ms | 4.64× | 50,000,000 output rows | [Experiment 04](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/04_join_cardinality) |
| 05 Incremental build | Full rebuild | 88.228 ms | 36.98× | 10,100,000 rows processed/written | [Experiment 05](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/05_incremental_build) |
| 05 Incremental build | Incremental append | 2.386 ms | 1.00× | 100,000 rows processed/written | [Experiment 05](https://github.com/daeusjorento/random_projects/tree/main/query_benchmarks/05_incremental_build) |

## Environment and methodology

- DuckDB 1.4.5
- Python 3.9.6
- macOS arm64
- 8 logical CPUs
- 16 GiB memory
- DuckDB fixed to 8 threads for experiments 02–05
- One unmeasured warm-up followed by 10 measured runs per variant
- Deterministic local synthetic data; no downloaded datasets or cloud services
- Every measured result verified
- `EXPLAIN ANALYZE` executed separately from timed runs where applicable

Experiment 01 predates the fixed-thread convention: it recorded a machine with 8 logical CPUs but allowed DuckDB to use its default thread setting. This should be disclosed when using its absolute timings. Relative runtimes should only be compared within an experiment, because the queries, data layouts, and measured operations differ substantially.

## Interpretation limits

The physical-organization experiment changes both row-group eligibility and compression/file size. The join-cardinality experiment changes both dimension size and joined output volume. The incremental-build experiment covers an append-only case and does not test merges, updates, deletes, late-arriving corrections, schema changes, or periodic full refreshes.
