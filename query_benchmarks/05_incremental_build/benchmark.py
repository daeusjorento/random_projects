import argparse
import csv
import os
from pathlib import Path
import platform
import random
import statistics
import time

import duckdb

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "data" / ".matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_HISTORICAL = 10_000_000
DEFAULT_NEW = 100_000
DEFAULT_THREADS = 8
RUNS = 10
SEED = 20260813
VARIANTS = ("full_rebuild", "incremental_append")


def positive_int(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical-rows", type=positive_int, default=DEFAULT_HISTORICAL)
    parser.add_argument("--new-rows", type=positive_int, default=DEFAULT_NEW)
    parser.add_argument("--threads", type=positive_int, default=DEFAULT_THREADS)
    return parser.parse_args()


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def create_sources(con, data_dir, historical_rows, new_rows):
    historical = data_dir / "historical.parquet"; new = data_dir / "new_date.parquet"
    historical.unlink(missing_ok=True); new.unlink(missing_ok=True)
    con.execute(f"""COPY (SELECT range::BIGINT AS id,
        DATE '2025-01-01' + (range % 100)::INTEGER AS event_date,
        (range % 1000000)::INTEGER AS customer_id,
        ((range * 17 + 23) % 10000)::INTEGER AS value FROM range({historical_rows}))
        TO {quote(historical)} (FORMAT PARQUET, COMPRESSION ZSTD)""")
    con.execute(f"""COPY (SELECT ({historical_rows} + range)::BIGINT AS id,
        DATE '2025-04-11' AS event_date,
        (({historical_rows} + range) % 1000000)::INTEGER AS customer_id,
        ((({historical_rows} + range) * 17 + 23) % 10000)::INTEGER AS value FROM range({new_rows}))
        TO {quote(new)} (FORMAT PARQUET, COMPRESSION ZSTD)""")
    return historical, new


def summary(con, relation):
    return con.execute(f"""SELECT COUNT(*), MIN(event_date), MAX(event_date),
        SUM(id), SUM(customer_id), SUM(value), bit_xor(hash(id,event_date,customer_id,value))
        FROM {relation}""").fetchone()


def run_statement(con, statement, expected, label, timed):
    con.execute("BEGIN TRANSACTION")
    try:
        start = time.perf_counter_ns(); con.execute(statement)
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        actual = summary(con, "target")
        if actual != expected:
            raise AssertionError(f"{label}: got {actual}, expected {expected}")
    finally:
        con.execute("ROLLBACK")
    return elapsed if timed else None


def profile(con, statement, expected, path):
    con.execute("BEGIN TRANSACTION")
    try:
        text = con.execute("EXPLAIN ANALYZE " + statement).fetchone()[1]
        actual = summary(con, "target")
        if actual != expected:
            raise AssertionError(f"profile {path.name} produced wrong target")
    finally:
        con.execute("ROLLBACK")
    text = text.replace(str(path.parents[1]), ".")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)


def chart(path, rows):
    labels = ["Full rebuild", "Incremental append"]
    values = [row["median_ms"] for row in rows]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, values, color=("#F28E2B", "#2878B5"))
    ax.bar_label(bars, fmt="%.3f ms", padding=3)
    ax.set(title="DuckDB incremental build benchmark", ylabel="Median runtime (ms)")
    ax.grid(axis="y", alpha=.3); fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def main():
    config = args(); base = Path(__file__).resolve().parent
    for name in ("data", "profiles", "charts"):
        (base / name).mkdir(parents=True, exist_ok=True)
    database = base / "data" / "incremental.duckdb"; database.unlink(missing_ok=True)
    con = duckdb.connect(str(database)); con.execute(f"SET threads={config.threads}")
    print(f"Generating {config.historical_rows:,} historical and {config.new_rows:,} new rows...", flush=True)
    historical, new = create_sources(con, base / "data", config.historical_rows, config.new_rows)
    con.execute(f"CREATE VIEW historical_source AS SELECT * FROM read_parquet({quote(historical)})")
    con.execute(f"CREATE VIEW new_source AS SELECT * FROM read_parquet({quote(new)})")
    con.execute("CREATE TABLE target AS SELECT * FROM historical_source")
    initial = summary(con, "target"); expected = summary(con, "(SELECT * FROM historical_source UNION ALL SELECT * FROM new_source)")
    if initial[0] != config.historical_rows or expected[0] != config.historical_rows + config.new_rows:
        raise AssertionError("source or initial target row count is incorrect")

    statements = {
        "full_rebuild": "CREATE OR REPLACE TABLE target AS SELECT * FROM historical_source UNION ALL SELECT * FROM new_source",
        "incremental_append": "INSERT INTO target SELECT * FROM new_source",
    }
    for name in VARIANTS:
        run_statement(con, statements[name], expected, name + " warm-up", timed=False)

    timings = {name: [] for name in VARIANTS}; rng = random.Random(SEED)
    for run in range(1, RUNS + 1):
        order = list(VARIANTS); rng.shuffle(order)
        for name in order:
            timings[name].append(run_statement(con, statements[name], expected, f"{name} run {run}", timed=True))

    rows = []
    for name in VARIANTS:
        profile(con, statements[name], expected, base / "profiles" / f"{name}.txt")
        values = timings[name]
        processed = config.historical_rows + config.new_rows if name == "full_rebuild" else config.new_rows
        row = {"variant": name, "historical_rows": config.historical_rows, "new_rows": config.new_rows,
               "rows_processed": processed, "rows_written": processed,
               "final_target_rows": expected[0], "runs": RUNS,
               "median_ms": round(statistics.median(values), 3), "min_ms": round(min(values), 3),
               "max_ms": round(max(values), 3), "duckdb_version": duckdb.__version__,
               "python_version": platform.python_version(), "thread_count": config.threads, "verified": True}
        rows.append(row)
        print(f"{name}: processed={processed:,}, median={row['median_ms']:.3f} ms, min={row['min_ms']:.3f}, max={row['max_ms']:.3f}", flush=True)
    save_csv(base / "results.csv", rows); chart(base / "charts" / "incremental_build_runtime.png", rows)
    con.close(); print("Every write verified and rolled back to the historical target.", flush=True)


if __name__ == "__main__":
    main()
