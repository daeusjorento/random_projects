# Row-count scaling results

| Rows | Median | Minimum | Maximum | Relative to 100K | Verified result |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100,000 | 0.191 ms | 0.179 ms | 0.272 ms | 1.0x | 49,950,000 |
| 1,000,000 | 0.427 ms | 0.410 ms | 0.514 ms | 2.2x | 499,500,000 |
| 10,000,000 | 2.433 ms | 2.375 ms | 2.652 ms | 12.7x | 4,995,000,000 |
| 30,000,000 | 7.154 ms | 6.975 ms | 7.436 ms | 37.5x | 14,985,000,000 |
| 100,000,000 | 27.410 ms | 25.939 ms | 32.943 ms | 143.5x | 49,950,000,000 |

The larger tables were close to linear: increasing from 10 million to 100 million rows added 10 times as many rows and took 11.3 times as long to query. The 10-million-to-30-million step was almost exactly proportional (3x the rows, 2.9x the runtime). The full 100,000-to-100-million comparison remains sublinear because fixed query overhead is a much larger share of runtime for the smallest tables.

Environment:

- DuckDB 1.4.5
- Python 3.9.6
- macOS arm64
- 8 logical CPUs
- 16 GiB memory

Each table received one warm-up query followed by 10 measured queries, and every result was verified. Table creation was measured separately and excluded from the query timings.
