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
ROW_GROUP_SIZE = 122_880
DATE_START = "2025-01-01"
FILTER_START = "2025-06-15"
FILTER_END_EXCLUSIVE = "2025-06-22"
ORGANIZATIONS = ("sorted_by_date", "random_order")


def positive_integer(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark Parquet row-group pruning with sorted and random data."
    )
    parser.add_argument("--rows", type=positive_integer, default=DEFAULT_ROWS)
    parser.add_argument("--threads", type=positive_integer, default=DEFAULT_THREADS)
    return parser.parse_args()


def sql_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def generated_rows_sql(row_count):
    return f"""
        SELECT
            range::BIGINT AS id,
            DATE '{DATE_START}' + (range % 365)::INTEGER AS event_date,
            (range % 1000000)::INTEGER AS customer_id,
            ((range * 17 + 23) % 10000)::INTEGER AS value
        FROM range({row_count})
    """


def create_parquet(connection, output_path, row_count, organization):
    output_path.unlink(missing_ok=True)
    if organization == "sorted_by_date":
        order_by = "event_date, id"
    elif organization == "random_order":
        order_by = "hash(id)"
    else:
        raise ValueError(f"Unknown organization: {organization}")

    connection.execute(
        f"""
        COPY (
            SELECT *
            FROM ({generated_rows_sql(row_count)}) AS generated
            ORDER BY {order_by}
        ) TO {sql_string(output_path)} (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE {ROW_GROUP_SIZE}
        )
        """
    )


def benchmark_query(parquet_path):
    return f"""
        SELECT COUNT(*), SUM(value)
        FROM read_parquet({sql_string(parquet_path)})
        WHERE event_date >= DATE '{FILTER_START}'
          AND event_date < DATE '{FILTER_END_EXCLUSIVE}';
    """


def logical_summary(connection, parquet_path):
    return connection.execute(
        f"""
        SELECT
            COUNT(*),
            MIN(event_date),
            MAX(event_date),
            SUM(id),
            SUM(customer_id),
            SUM(value),
            bit_xor(hash(id, event_date, customer_id, value))
        FROM read_parquet({sql_string(parquet_path)});
        """
    ).fetchone()


def execute_and_verify(connection, query, expected, label):
    actual = connection.execute(query).fetchone()
    if actual is None or len(actual) != 2:
        actual_count = 0 if actual is None else len(actual)
        raise AssertionError(f"{label} returned {actual_count} values; expected 2")
    if tuple(actual) != expected:
        raise AssertionError(f"{label} returned {actual}; expected {expected}")
    return tuple(actual)


def collect_row_group_stats(connection, parquet_path, organization):
    rows = connection.execute(
        f"""
        SELECT
            row_group_id,
            row_group_num_rows,
            CAST(stats_min AS DATE) AS min_event_date,
            CAST(stats_max AS DATE) AS max_event_date,
            CAST(stats_min AS DATE) < DATE '{FILTER_END_EXCLUSIVE}'
                AND CAST(stats_max AS DATE) >= DATE '{FILTER_START}' AS overlaps_filter
        FROM parquet_metadata({sql_string(parquet_path)})
        WHERE path_in_schema = 'event_date'
        ORDER BY row_group_id;
        """
    ).fetchall()
    if not rows:
        raise AssertionError(f"No event_date row-group metadata found for {parquet_path}")

    return [
        {
            "physical_organization": organization,
            "row_group_id": row_group_id,
            "row_group_rows": row_group_rows,
            "min_event_date": min_event_date.isoformat(),
            "max_event_date": max_event_date.isoformat(),
            "overlaps_filter": bool(overlaps_filter),
        }
        for (
            row_group_id,
            row_group_rows,
            min_event_date,
            max_event_date,
            overlaps_filter,
        ) in rows
    ]


def profile_query(connection, query, output_path):
    profile = connection.execute(f"EXPLAIN ANALYZE {query}").fetchone()[1]
    profile = profile.replace(str(output_path.parents[1]), ".")
    profile = "\n".join(line.rstrip() for line in profile.splitlines())
    output_path.write_text(profile.rstrip() + "\n", encoding="utf-8")


def write_csv(output_path, rows):
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def write_chart(output_path, results):
    labels = [
        "Sorted by date" if result["physical_organization"] == "sorted_by_date"
        else "Random order"
        for result in results
    ]
    medians = [result["median_ms"] for result in results]

    figure, axis = plt.subplots(figsize=(7, 4.5))
    bars = axis.bar(labels, medians, color=("#2878B5", "#F28E2B"))
    axis.bar_label(bars, fmt="%.3f ms", padding=3)
    axis.set_title("Parquet physical organization benchmark")
    axis.set_ylabel("Median runtime (ms)")
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

    paths = {
        "sorted_by_date": data_dir / "sorted_by_date.parquet",
        "random_order": data_dir / "random_order.parquet",
    }
    connection = duckdb.connect()
    connection.execute(f"SET threads = {args.threads}")

    for organization in ORGANIZATIONS:
        print(f"Generating {organization}.parquet with {args.rows:,} rows...", flush=True)
        create_parquet(connection, paths[organization], args.rows, organization)
        size_mib = paths[organization].stat().st_size / (1024 * 1024)
        print(f"Generated {organization}.parquet: {size_mib:.2f} MiB", flush=True)

    summaries = {
        organization: logical_summary(connection, paths[organization])
        for organization in ORGANIZATIONS
    }
    if summaries["sorted_by_date"] != summaries["random_order"]:
        raise AssertionError(f"Logical data differs: {summaries}")
    if summaries["sorted_by_date"][0] != args.rows:
        raise AssertionError(
            f"Files contain {summaries['sorted_by_date'][0]} rows; expected {args.rows}"
        )

    queries = {
        organization: benchmark_query(paths[organization])
        for organization in ORGANIZATIONS
    }
    sorted_warm_up = connection.execute(queries["sorted_by_date"]).fetchone()
    if sorted_warm_up is None or len(sorted_warm_up) != 2:
        actual_count = 0 if sorted_warm_up is None else len(sorted_warm_up)
        raise AssertionError(
            f"sorted warm-up returned {actual_count} values; expected 2"
        )
    expected = tuple(sorted_warm_up)
    execute_and_verify(connection, queries["random_order"], expected, "random warm-up")

    timings = {organization: [] for organization in ORGANIZATIONS}
    rng = random.Random(RANDOM_SEED)
    for round_number in range(1, MEASURED_RUNS + 1):
        order = list(ORGANIZATIONS)
        rng.shuffle(order)
        for organization in order:
            start = time.perf_counter_ns()
            execute_and_verify(
                connection,
                queries[organization],
                expected,
                f"{organization} measured run {round_number}",
            )
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            timings[organization].append(elapsed_ms)

    row_group_rows = []
    for organization in ORGANIZATIONS:
        row_group_rows.extend(
            collect_row_group_stats(connection, paths[organization], organization)
        )
    write_csv(experiment_dir / "row_group_stats.csv", row_group_rows)

    profile_query(
        connection,
        queries["sorted_by_date"],
        profiles_dir / "sorted_by_date.txt",
    )
    profile_query(
        connection,
        queries["random_order"],
        profiles_dir / "random_order.txt",
    )

    results = []
    for organization in ORGANIZATIONS:
        organization_groups = [
            row for row in row_group_rows
            if row["physical_organization"] == organization
        ]
        run_times = timings[organization]
        result = {
            "physical_organization": organization,
            "input_rows": args.rows,
            "matching_rows": expected[0],
            "runs": MEASURED_RUNS,
            "total_row_groups": len(organization_groups),
            "overlapping_row_groups": sum(
                row["overlaps_filter"] for row in organization_groups
            ),
            "median_ms": round(statistics.median(run_times), 3),
            "min_ms": round(min(run_times), 3),
            "max_ms": round(max(run_times), 3),
            "parquet_file_size_bytes": paths[organization].stat().st_size,
            "duckdb_version": duckdb.__version__,
            "python_version": platform.python_version(),
            "thread_count": args.threads,
            "verified": True,
        }
        results.append(result)
        print(
            f"{organization}: median={result['median_ms']:.3f} ms, "
            f"min={result['min_ms']:.3f} ms, max={result['max_ms']:.3f} ms, "
            f"eligible row groups={result['overlapping_row_groups']}/"
            f"{result['total_row_groups']}",
            flush=True,
        )

    write_csv(experiment_dir / "results.csv", results)
    write_chart(charts_dir / "physical_organization_runtime.png", results)
    connection.close()
    print("Logical data, filtered results, timings, and metadata verified.", flush=True)


if __name__ == "__main__":
    main()
