
# Serial Fraction Estimation – Strong Scaling Analysis

## 1. Objective

This analysis estimates the serial fraction of the railway simulation using two independent approaches:

1. A measured effective serial fraction derived from parallel speedups using Amdahl's law.
2. A profile-based estimate derived from the sequential execution-time breakdown.

The purpose is to compare the two estimates and understand how measured parallel performance relates to the sequential profile.

## 2. Experimental Setup

The strong-scaling experiment used:

- 100,000 scenarios.
- 60 railway stations.
- Seed: 42.
- Execution node: `haskell`.
- Python implementation.
- Five repetitions per configuration.

The experiment consisted of seven separate Slurm jobs: one sequential configuration and six multiprocessing configurations (1, 2, 4, 8, 16 and 32 workers). Each job executed five repetitions of its assigned configuration.

The timing analysis uses the median of the five repetitions for each configuration.

**Baseline:** One-worker multiprocessing, with a median elapsed time of 590.5819 seconds. This is the appropriate baseline because the parallel speedups compare multiprocessing configurations against one another.

## 3. Method 1 – Measured Effective Serial Fraction

### 3.1 Methodology

The measured speedup is calculated as:

\[
S(p)=\frac{T_1}{T_p}
\]

Where:

- \(T_1\) is the median elapsed time with one multiprocessing worker.
- \(T_p\) is the median elapsed time with \(p\) workers.

Amdahl's law is:

\[
S(p)=\frac{1}{f+\frac{1-f}{p}}
\]

Rearranging it gives the effective serial fraction:

\[
f_{\mathrm{eff}}(p)=\frac{p/S(p)-1}{p-1}
\]

Parallel efficiency is calculated as:

\[
E(p)=\frac{S(p)}{p}\times100
\]

### 3.2 Results

| Workers | Median elapsed time (s) | Speedup | Efficiency | Effective serial fraction |
|---:|---:|---:|---:|---:|
| 8 | 92.0611 | 6.415x | 80.19% | 3.529% |
| 16 | 47.6382 | 12.397x | 77.48% | 1.937% |
| 32 | 24.6972 | 23.913x | 74.73% | 1.091% |

### 3.3 Example calculation: 32 workers

First, calculate speedup:

\[
S(32)=\frac{590.5819}{24.6972}=23.913
\]

Then calculate efficiency:

\[
E(32)=\frac{23.913}{32}\times100=74.73\%
\]

Finally, calculate the effective serial fraction:

\[
f_{\mathrm{eff}}(32)=\frac{32/23.913-1}{31}
\]

\[
f_{\mathrm{eff}}(32)=0.01091=1.091\%
\]

This means that the measured performance at 32 workers corresponds to an effective serial fraction of approximately 1.091% under Amdahl's model.

## 4. Method 2 – Profile-Based Estimate

### 4.1 Methodology

The second approach uses the sequential profiling results documented in `docs/profiling/profiling.md`.

The profile divides execution time into loading, scenario generation, computation and writing.

For this estimate, the non-compute proportion is calculated as:

\[
f_{\mathrm{profile}}=
\frac{T_{\mathrm{load}}+T_{\mathrm{generation}}+T_{\mathrm{write}}}{T_{\mathrm{total}}}
\]

The measured values are:

| Component | Time (s) |
|---|---:|
| Data loading | 0.002 |
| Scenario generation | 3.13 |
| Writing results | 0.15 |
| Total sequential wall time | 603.7 |

Therefore:

\[
f_{\mathrm{profile}}=\frac{0.002+3.13+0.15}{603.7}
\]

\[
f_{\mathrm{profile}}=\frac{3.282}{603.7}=0.005436
\]

\[
\boxed{f_{\mathrm{profile}}=0.5436\%}
\]

### 4.2 Interpretation

This value is a profile-based proxy rather than an exact theoretical serial fraction. It represents the proportion of sequential execution time classified as loading, scenario generation and writing in the profiling breakdown.

These activities are not necessarily all inherently sequential or impossible to parallelise. Therefore, this estimate should not be interpreted as a precise measurement of the algorithm's unavoidable serial work.

## 5. Comparison of Both Methods

| Estimation method | Estimated fraction |
|---|---:|
| Profile-based non-compute proportion | 0.5436% |
| Effective Amdahl fraction (8 workers) | 3.529% |
| Effective Amdahl fraction (16 workers) | 1.937% |
| Effective Amdahl fraction (32 workers) | 1.091% |

Both estimates are below 4%, but they represent different measurements. The profile-based method classifies execution time into program activities, while the effective Amdahl estimate reflects observed speedup and can absorb implementation and system overheads.

The effective fraction also decreases as the worker count increases. This indicates that it should not be interpreted as one fixed theoretical serial fraction. The ideal Amdahl model assumes a constant serial fraction, whereas real parallel executions can be affected by worker startup, scheduling, resource contention and other overheads.

## 6. Parallel Execution Time Breakdown

The following table reports the median timing of each component for the multiprocessing configurations.

| Workers | Load (s) | Compute (s) | Write (s) | Pool startup (s) | Total elapsed (s) |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.0017 | 590.3595 | 0.0805 | 0.1029 | 590.5819 |
| 2 | 0.0017 | 296.5844 | 0.0811 | 0.0979 | 296.8053 |
| 4 | 0.0017 | 148.9509 | 0.0808 | 0.1690 | 149.2420 |
| 8 | 0.0017 | 91.6045 | 0.0814 | 0.3385 | 92.0611 |
| 16 | 0.0017 | 46.8457 | 0.0827 | 0.6660 | 47.6382 |
| 32 | 0.0017 | 23.2464 | 0.0821 | 1.3275 | 24.6972 |

The computation time decreases substantially as the number of workers increases. In contrast, loading and writing times remain very small.

Pool startup time increases at higher worker counts, reaching 1.3275 seconds at 32 workers. This is one directly measured source of overhead.

**Important timing note:** Total elapsed time already includes pool startup. The startup column is shown separately for analysis and must not be added to elapsed time again. The median values of individual timing columns may also not sum exactly to the median elapsed time because each column's median is calculated independently.

## 7. Overall Interpretation

The results show that the railway simulation achieves substantial parallel speedup.

At 32 workers, the execution time falls from 590.5819 seconds with one multiprocessing worker to 24.6972 seconds, achieving a speedup of approximately **23.91x** and an efficiency of **74.73%**.

The effective Amdahl estimate at this configuration is 1.091%, while the profile-based non-compute estimate is 0.5436%.

Although both estimates are below 2%, they represent different measurements and should not be interpreted as equivalent. The first reflects observed parallel performance, while the second reflects the sequential profiling breakdown.

The reduction in parallel efficiency as worker count increases suggests diminishing returns at higher worker counts. Increasing pool startup time is one observed overhead, although the available measurements do not establish that it is the only cause.

## 8. Limitations

- The effective serial fraction is an equivalent estimate derived from measured speedups, not a direct measurement of the algorithm's theoretically unavoidable sequential work.
- The profile-based estimate depends on how the program's execution activities are classified.
- The two methods use different timing contexts: the profile-based estimate comes from the sequential profiling run, while the effective estimates use multiprocessing benchmark timings.
- System effects, including worker startup, scheduling and resource contention, can influence measured speedups.
- Five repetitions per configuration provide a median, but do not eliminate all environmental variation.
- The effective fraction varies with worker count, so it should not be presented as a single constant serial fraction.

## 9. Reproducibility and References

The calculations can be reproduced with:

```bash
python scripts/estimate_serial_fraction.py
```

Relevant project files:

- `scripts/estimate_serial_fraction.py` – calculation script.
- `docs/timings/strong_scaling_haskell.csv` – raw benchmark measurements.
- `docs/profiling/profiling.md` – sequential profiling results.
- `docs/benchmarking.md` – benchmark methodology and configuration.
- `docs/timing_schema.md` – timing-column definitions.
- `slurm/submit_strong_scaling.sh` – submits the seven benchmark jobs.
- `slurm/benchmark.sh` – executes five repetitions per configuration.

## 10. AI Use and Acknowledgement

ChatGPT (OpenAI) assisted with structuring the serial-fraction estimation methodology, explaining Amdahl's law, developing the calculation script and drafting this documentation. The calculations, code and interpretations were reviewed, adapted and tested against the project's benchmark data.

