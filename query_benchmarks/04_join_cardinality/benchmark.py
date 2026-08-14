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


DEFAULT_ROWS = 10_000_000
DEFAULT_THREADS = 8
RUNS = 10
SEED = 20260813
VARIANTS = (("one_match_per_key", 1), ("five_matches_per_key", 5))


def positive_int(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=positive_int, default=DEFAULT_ROWS)
    parser.add_argument("--threads", type=positive_int, default=DEFAULT_THREADS)
    return parser.parse_args()


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def write_data(con, data_dir, fact_rows, keys):
    files = {
        "fact": data_dir / "fact.parquet",
        "one_match_per_key": data_dir / "dimension_one.parquet",
        "five_matches_per_key": data_dir / "dimension_five.parquet",
    }
    for path in files.values():
        path.unlink(missing_ok=True)
    con.execute(f"""COPY (SELECT range::BIGINT id, (range % {keys})::INTEGER join_key,
        ((range * 17 + 23) % 10000)::INTEGER fact_value FROM range({fact_rows}))
        TO {quote(files['fact'])} (FORMAT PARQUET, COMPRESSION ZSTD)""")
    for name, matches in VARIANTS:
        con.execute(f"""COPY (SELECT key_range::INTEGER join_key, variant_range::INTEGER variant,
            ((key_range * 13 + variant_range * 7) % 1000)::INTEGER dim_value
            FROM range({keys}) keys(key_range), range({matches}) variants(variant_range))
            TO {quote(files[name])} (FORMAT PARQUET, COMPRESSION ZSTD)""")
    return files


def join_query(fact, dimension):
    return f"""SELECT COUNT(*), SUM(f.fact_value + d.dim_value + d.variant)
        FROM read_parquet({quote(fact)}) f
        JOIN read_parquet({quote(dimension)}) d USING (join_key);"""


def independent_expected(con, fact, dimension, matches):
    fact_count, fact_sum = con.execute(
        f"SELECT COUNT(*), SUM(fact_value) FROM read_parquet({quote(fact)})"
    ).fetchone()
    dim_count = con.execute(
        f"SELECT COUNT(*) FROM read_parquet({quote(dimension)})"
    ).fetchone()[0]
    weighted_dim_sum = con.execute(f"""SELECT SUM((d.dim_value + d.variant) * f.key_count)
        FROM read_parquet({quote(dimension)}) d
        JOIN (SELECT join_key, COUNT(*) key_count FROM read_parquet({quote(fact)}) GROUP BY join_key) f
        USING (join_key)""").fetchone()[0]
    return (fact_count * matches, fact_sum * matches + weighted_dim_sum), dim_count


def verified(con, query, expected, label):
    result = con.execute(query).fetchone()
    if result is None or len(result) != 2 or tuple(result) != expected:
        raise AssertionError(f"{label}: got {result}, expected {expected}")
    return tuple(result)


def profile(con, query, path):
    text = con.execute("EXPLAIN ANALYZE " + query).fetchone()[1]
    text = text.replace(str(path.parents[1]), ".")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)


def chart(path, rows):
    labels = ["1 match/key", "5 matches/key"]
    values = [row["median_ms"] for row in rows]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, values, color=("#2878B5", "#F28E2B"))
    ax.bar_label(bars, fmt="%.3f ms", padding=3)
    ax.set(title="DuckDB join cardinality benchmark", ylabel="Median runtime (ms)")
    ax.grid(axis="y", alpha=.3); fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def main():
    config = args()
    base = Path(__file__).resolve().parent
    for name in ("data", "profiles", "charts"):
        (base / name).mkdir(parents=True, exist_ok=True)
    keys = min(1_000_000, max(1, config.rows // 10))
    con = duckdb.connect(); con.execute(f"SET threads={config.threads}")
    print(f"Generating {config.rows:,} fact rows and {keys:,} keys...", flush=True)
    files = write_data(con, base / "data", config.rows, keys)
    queries = {name: join_query(files["fact"], files[name]) for name, _ in VARIANTS}
    expected = {}; dimension_rows = {}
    for name, matches in VARIANTS:
        expected[name], dimension_rows[name] = independent_expected(con, files["fact"], files[name], matches)
        verified(con, queries[name], expected[name], name + " warm-up")

    timings = {name: [] for name, _ in VARIANTS}; rng = random.Random(SEED)
    for run in range(1, RUNS + 1):
        order = [name for name, _ in VARIANTS]; rng.shuffle(order)
        for name in order:
            start = time.perf_counter_ns(); verified(con, queries[name], expected[name], f"{name} run {run}")
            timings[name].append((time.perf_counter_ns() - start) / 1_000_000)

    rows = []
    for name, matches in VARIANTS:
        profile(con, queries[name], base / "profiles" / f"{name}.txt")
        values = timings[name]
        row = {"variant": name, "fact_rows": config.rows, "dimension_rows": dimension_rows[name],
               "distinct_join_keys": keys, "matches_per_key": matches, "output_rows": expected[name][0],
               "fanout_multiplier": matches, "runs": RUNS, "median_ms": round(statistics.median(values), 3),
               "min_ms": round(min(values), 3), "max_ms": round(max(values), 3),
               "duckdb_version": duckdb.__version__, "python_version": platform.python_version(),
               "thread_count": config.threads, "verified": True}
        rows.append(row)
        print(f"{name}: output={row['output_rows']:,}, median={row['median_ms']:.3f} ms, min={row['min_ms']:.3f}, max={row['max_ms']:.3f}", flush=True)
    save_csv(base / "results.csv", rows); chart(base / "charts" / "join_cardinality_runtime.png", rows)
    con.close(); print("All join results independently verified.", flush=True)


if __name__ == "__main__":
    main()
