# 14.5 Initial Scale-Up Consideration Note

Measured throughput (`telltale.cli profile`, `results/profiling.json`): monitor evidence
computation runs at roughly 117,000 transactions per second at a 1,000-row window, rising to about
650,000 to 800,000 transactions per second at window sizes from 10,000 to 1,000,000 rows (the exact
number varies with the bin-count overhead relative to the vectorised work, not a strict monotonic
curve). At the PRD's default window size of 2,000 rows, one window's monitor computation takes about
5.6 ms, comfortably inside the 100 ms budget (PR6). A full retrain needing a monitor reference (6
model fits) costs about 15.5 seconds; one that does not (B1, B2) costs about 2.8 seconds.

**What changes at millions of transactions per day.** This project's windows are an in-memory numpy
array scored as a single batch. A real issuer processing millions to tens of millions of
transactions a day would not do that for several reasons:

- **Streaming windows.** A single undivided daily batch of 10 million rows would take on the order
  of 15 seconds of monitor compute alone (extrapolating the measured 1.5 seconds at 1,000,000 rows),
  which is workable as a nightly batch job but not as anything closer to real time; a real deployment
  would window by a shorter interval (hourly, or a fixed transaction count) and monitor continuously
  rather than once a day.
- **Feature stores.** The reference distribution and the null calibration both assume the monitor
  can see a consistent, versioned snapshot of recent feature values. At production scale this
  typically means a feature store rather than recomputing features from raw transaction logs on
  each window.
- **Approximate quantiles.** The PSI bin edges here are computed from an exact quantile of the full
  reference pool, cheap at tens of thousands of rows. At millions of rows per window, an approximate
  quantile sketch (e.g. t-digest or a streaming histogram) would keep bin-edge computation from
  becoming the bottleneck as window size grows, without materially changing the PSI statistic itself.
- **Retrain scheduling.** A 15.5-second retrain is trivial at this project's scale; at production
  data volumes a full refit on millions of rows would take meaningfully longer, so the deferred-
  retrain design (wait for alarm time + D + m, never retrain more than the evidence justifies)
  matters more, not less, since unnecessary retrains become proportionally more expensive.
- **Monitoring many models at once.** A platform running this approach across many models (one per
  product line, region, or channel) multiplies both the monitor compute and the retrain compute
  linearly in the number of models monitored; the per-model costs measured here are the right unit
  to multiply by a deployment's actual model count when budgeting infrastructure.
