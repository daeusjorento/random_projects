import csv
import os
import platform
import shutil
import statistics
import tempfile
import time

import duckdb


ROW_COUNTS = (100_000, 1_000_000, 10_000_000, 30_000_000, 100_000_000)
MEASURED_RUNS = 10
MIN_FREE_DISK_BYTES = 10 * 1024**3


def expected_sum(row_count):
    cycles, remainder = divmod(row_count, 1_000)
    return cycles * sum(range(1_000)) + sum(range(remainder))


def total_memory_bytes():
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return ""


def main():
    machine = {
        "duckdb_version": duckdb.__version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or "",
        "memory_bytes": total_memory_bytes(),
    }
    results = []

    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = os.path.join(temp_dir, "benchmark.duckdb")
        connection = duckdb.connect(database_path)

        for row_count in ROW_COUNTS:
            free_disk_bytes = shutil.disk_usage(temp_dir).free
            if free_disk_bytes < MIN_FREE_DISK_BYTES:
                raise RuntimeError(
                    f"Only {free_disk_bytes / 1024**3:.1f} GiB of disk space remains; "
                    "stopping before creating another table."
                )

            table_name = f"rows_{row_count}"
            create_start = time.perf_counter_ns()
            connection.execute(
                f"""
                CREATE TABLE {table_name} AS
                SELECT
                    range::INTEGER AS id,
                    (range % 100)::INTEGER AS category,
                    (range % 1000)::DOUBLE AS value
                FROM range({row_count})
                """
            )
            create_ms = (time.perf_counter_ns() - create_start) / 1_000_000

            query = f"SELECT SUM(value) FROM {table_name};"
            expected = float(expected_sum(row_count))

            warm_up_result = connection.execute(query).fetchone()[0]
            if warm_up_result != expected:
                raise AssertionError(
                    f"Warm-up for {table_name} returned {warm_up_result}, expected {expected}"
                )

            timings_ms = []
            for run_number in range(1, MEASURED_RUNS + 1):
                start = time.perf_counter_ns()
                actual = connection.execute(query).fetchone()[0]
                elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

                if actual != expected:
                    raise AssertionError(
                        f"Run {run_number} for {table_name} returned {actual}, "
                        f"expected {expected}"
                    )
                timings_ms.append(elapsed_ms)

            result = {
                "table_name": table_name,
                "row_count": row_count,
                "median_ms": round(statistics.median(timings_ms), 3),
                "min_ms": round(min(timings_ms), 3),
                "max_ms": round(max(timings_ms), 3),
                "create_ms": round(create_ms, 3),
                "result": int(expected),
                "expected_result": int(expected),
                "verified": True,
                "measured_runs": MEASURED_RUNS,
                **machine,
            }
            results.append(result)
            print(
                f"{table_name}: median={result['median_ms']:.3f} ms, "
                f"min={result['min_ms']:.3f} ms, max={result['max_ms']:.3f} ms, "
                f"created={result['create_ms']:.3f} ms, "
                f"result={result['result']} (verified)"
            )
            connection.execute(f"DROP TABLE {table_name}")

        connection.close()

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.csv")
    with open(output_path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file, fieldnames=results[0].keys(), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDuckDB {machine['duckdb_version']} | Python {machine['python_version']}")
    print(
        f"{machine['platform']} | {machine['machine']} | "
        f"{machine['cpu_count']} logical CPUs | {machine['memory_bytes']} bytes memory"
    )
    print(f"Results written to {output_path}")


if __name__ == "__main__":
    main()
