# SQL table-size benchmark

This small benchmark measures how long DuckDB takes to run `SELECT SUM(value)` as a table grows from 100,000 to 1,000,000 to 10,000,000 rows.

The script creates three physical DuckDB tables locally. Each table has the same columns: integer `id`, integer `category` from 0 to 99, and numeric `value`. All data is generated inside DuckDB with `range()`; no dataset is downloaded. Table creation is not timed. For each table, the script runs one unmeasured warm-up query and then 10 measured queries, verifies every result, and writes the median, minimum, and maximum runtime to `results.csv`.

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

The relative differences between the three table sizes are more useful: they show how the same query, schema, data pattern, software environment, and machine respond as row count increases.
