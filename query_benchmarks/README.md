# Query benchmarks

This directory contains reproducible local experiments investigating what affects SQL query performance. Each experiment keeps its implementation intentionally small, generates its own data locally, and records enough environment information to interpret the results.

## Experiments

1. [`01_row_count`](01_row_count/) — measures how the runtime of `SELECT SUM(value)` changes as a DuckDB table grows from 100,000 to 1,000,000 to 10,000,000 rows.
