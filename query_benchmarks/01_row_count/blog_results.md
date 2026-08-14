# Baseline results

| Rows | Median | Minimum | Maximum | Verified result |
| ---: | ---: | ---: | ---: | ---: |
| 100,000 | 0.176 ms | 0.164 ms | 0.222 ms | 49,950,000 |
| 1,000,000 | 0.431 ms | 0.408 ms | 0.486 ms | 499,500,000 |
| 10,000,000 | 2.494 ms | 2.371 ms | 2.965 ms | 4,995,000,000 |

Environment:

- DuckDB 1.4.5
- Python 3.9.6
- macOS arm64
- 8 logical CPUs
- 16 GiB memory

Each table received one warm-up query followed by 10 measured queries, and every result was verified.
