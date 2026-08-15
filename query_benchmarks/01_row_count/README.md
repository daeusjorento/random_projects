# SQL table-size benchmark

This small benchmark measures how long DuckDB takes to run `SELECT SUM(value)` as a table grows from 100,000 to 100,000,000 rows.

The script creates five physical DuckDB tables locally, one at a time, and drops each table after measuring it to bound active storage. Each table has the same columns: integer `id`, integer `category` from 0 to 99, and numeric `value`. All data is generated inside DuckDB with `range()`; no dataset is downloaded. Table creation is recorded separately and is not included in query runtime. For each table, the script runs one unmeasured warm-up query and then 10 measured queries, verifies every result, and writes the creation time plus median, minimum, and maximum query runtime to `results.csv`. The run stops before creating another table if less than 10 GiB of disk space remains.

## Run it

Python 3.9 or newer is recommended.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python benchmark.py
```

The temporary DuckDB database is deleted automatically after the benchmark. Only the code and the small `results.csv` output need to be committed to GitHub.

## Interpreting the results

Absolute runtimes depend on the machine, operating system, CPU load, memory bandwidth, DuckDB version, and other local conditions. Results from different machines should therefore not be treated as directly comparable.

The relative differences between the five table sizes are more useful: they show how the same query, schema, data pattern, software environment, and machine respond as row count increases. Fixed query overhead dominates the smallest tables, so the 10-million-to-100-million-row comparison is more informative about large-table scaling than the 100,000-row baseline.
