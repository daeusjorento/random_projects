import argparse
import csv
import os
from pathlib import Path
import platform
import random
import statistics
import time

import duckdb

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(__file__).resolve().parent / "data" / ".matplotlib")
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_ROWS = 10_000_000
DEFAULT_THREADS = 8
MEASURED_RUNS = 10
RANDOM_SEED = 20260813
COLUMN_COUNTS = (1, 5, 25)
COLUMN_NAMES = tuple(f"value_{number:02d}" for number in range(1, 26))


def positive_integer(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark DuckDB column pruning with a local Parquet file."
    )
    parser.add_argument("--rows", type=positive_integer, default=DEFAULT_ROWS)
    parser.add_argument("--threads", type=positive_integer, default=DEFAULT_THREADS)
    return parser.parse_args()


def sql_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def create_dataset(connection, parquet_path, row_count):
    parquet_path.unlink(missing_ok=True)
    measurements = ",\n                    ".join(
        f"((range + {number}) % 1000)::INTEGER AS value_{number:02d}"
        for number in range(1, 26)
    )
    connection.execute(
        f"""
        COPY (
            SELECT
                range::INTEGER AS id,
                {measurements}
            FROM range({row_count})
        ) TO {sql_string(parquet_path)} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )


def expected_sum(row_count, column_number):
    cycles, remainder = divmod(row_count, 1000)
    remainder_sum = sum((row + column_number) % 1000 for row in range(remainder))
    return cycles * 499_500 + remainder_sum


def query_for(parquet_path, column_count):
    aggregates = ", ".join(
        f"SUM({column_name})" for column_name in COLUMN_NAMES[:column_count]
    )
    return f"SELECT {aggregates} FROM read_parquet({sql_string(parquet_path)});"


def expected_result(row_count, column_count):
    return tuple(
        expected_sum(row_count, column_number)
        for column_number in range(1, column_count + 1)
    )


def execute_and_verify(connection, query, expected, label):
    actual = connection.execute(query).fetchone()
    if actual is None or len(actual) != len(expected):
        actual_count = 0 if actual is None else len(actual)
        raise AssertionError(
            f"{label} returned {actual_count} aggregates; expected {len(expected)}"
        )
    if tuple(actual) != expected:
        raise AssertionError(f"{label} returned {actual}; expected {expected}")
    return tuple(actual)


def profile_and_verify(connection, query, selected_columns, profile_path):
    profile = connection.execute(f"EXPLAIN ANALYZE {query}").fetchone()[1]
    profile = profile.replace(str(profile_path.parents[1]), ".")
    profile_path.write_text(profile.rstrip() + "\n", encoding="utf-8")

    missing = [column for column in selected_columns if column not in profile]
    unselected = [column for column in COLUMN_NAMES if column not in selected_columns]
    unexpected = [column for column in unselected if column in profile]
    if missing or unexpected:
        raise AssertionError(
            f"Projection check failed for {profile_path.name}: "
            f"missing={missing}, unexpected={unexpected}"
        )


def write_results(output_path, results):
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)


def write_chart(output_path, results):
    columns = [result["columns_read"] for result in results]
    medians = [result["median_ms"] for result in results]

    figure, axis = plt.subplots(figsize=(7, 4.5))
    axis.plot(columns, medians, marker="o", linewidth=2)
    axis.set_title("DuckDB column pruning benchmark")
    axis.set_xlabel("Measurement columns read")
    axis.set_ylabel("Median runtime (ms)")
    axis.set_xticks(columns)
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def main():
    args = parse_args()
    experiment_dir = Path(__file__).resolve().parent
    data_dir = experiment_dir / "data"
    profiles_dir = experiment_dir / "profiles"
    charts_dir = experiment_dir / "charts"
    for directory in (data_dir, profiles_dir, charts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    parquet_path = data_dir / "column_pruning.parquet"
    connection = duckdb.connect()
    connection.execute(f"SET threads = {args.threads}")

    print(f"Generating {args.rows:,} rows at {parquet_path}...")
    create_dataset(connection, parquet_path, args.rows)
    parquet_size = parquet_path.stat().st_size
    print(f"Parquet size: {parquet_size / (1024 * 1024):.2f} MiB")

    queries = {
        count: query_for(parquet_path, count) for count in COLUMN_COUNTS
    }
    expected = {
        count: expected_result(args.rows, count) for count in COLUMN_COUNTS
    }

    for count in COLUMN_COUNTS:
        execute_and_verify(
            connection, queries[count], expected[count], f"{count}-column warm-up"
        )

    timings = {count: [] for count in COLUMN_COUNTS}
    rng = random.Random(RANDOM_SEED)
    for round_number in range(1, MEASURED_RUNS + 1):
        order = list(COLUMN_COUNTS)
        rng.shuffle(order)
        for count in order:
            start = time.perf_counter_ns()
            execute_and_verify(
                connection,
                queries[count],
                expected[count],
                f"{count}-column measured run {round_number}",
            )
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            timings[count].append(elapsed_ms)

    profile_names = {
        1: "01_column.txt",
        5: "05_columns.txt",
        25: "25_columns.txt",
    }
    for count in COLUMN_COUNTS:
        profile_and_verify(
            connection,
            queries[count],
            COLUMN_NAMES[:count],
            profiles_dir / profile_names[count],
        )

    results = []
    for count in COLUMN_COUNTS:
        run_times = timings[count]
        result = {
            "rows": args.rows,
            "columns_read": count,
            "runs": MEASURED_RUNS,
            "median_ms": round(statistics.median(run_times), 3),
            "min_ms": round(min(run_times), 3),
            "max_ms": round(max(run_times), 3),
            "parquet_file_size_bytes": parquet_size,
            "duckdb_version": duckdb.__version__,
            "python_version": platform.python_version(),
            "thread_count": args.threads,
            "verified": True,
        }
        results.append(result)
        print(
            f"{count:>2} columns: median={result['median_ms']:.3f} ms, "
            f"min={result['min_ms']:.3f} ms, max={result['max_ms']:.3f} ms"
        )

    write_results(experiment_dir / "results.csv", results)
    write_chart(charts_dir / "column_pruning_runtime.png", results)
    connection.close()
    print("All warm-up, measured, and profile results verified.")


if __name__ == "__main__":
    main()
