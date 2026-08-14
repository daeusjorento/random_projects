# Query benchmarks

This directory contains reproducible local experiments investigating what affects SQL query performance. Each experiment keeps its implementation intentionally small, generates its own data locally, and records enough environment information to interpret the results.

## Experiments

1. [`01_row_count`](01_row_count/) — measures how the runtime of `SELECT SUM(value)` changes as a DuckDB table grows from 100,000 to 1,000,000 to 10,000,000 rows.
2. [`02_column_pruning`](02_column_pruning/) — measures how reading and aggregating 1, 5, or 25 integer columns from the same Parquet file affects DuckDB query performance.
3. [`03_physical_organization`](03_physical_organization/) — measures how date-sorted and deterministically randomized Parquet layouts affect row-group eligibility and filtered-query runtime.
4. [`04_join_cardinality`](04_join_cardinality/) — measures how one versus five dimension matches per key changes join output cardinality and runtime.
