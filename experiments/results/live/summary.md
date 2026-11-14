# Live evaluation summary

Fault runs: r1, r2, r3 · fault-free runs: n1 · model: live-pca 1.1.0. Values are mean ± standard deviation over runs.

| Metric | Value |
|---|---|
| Incidents detected | 100.0% ± 0.0 |
| Detection delay (first anomaly after fault start) | 52 s ± 7 |
| Alert delay (first alert after fault start) | 52 s ± 7 |
| Precision (faulty service's minutes) | 54.5% ± 0.6 |
| Recall | 84.5% ± 7.5 |
| F1 | 0.66 ± 0.02 |
| Recall, minutes fully inside a fault | 100.0% ± 0.0 |
| Precision counting reactions near incidents | 100.0% ± 0.0 |
| False-alarm rate, quiet minutes | 0.0% ± 0.0 |
| Anomalies per incident | 6.67 ± 0.76 |
| Alerts per incident | 2.53 ± 0.12 |
| Alerts outside incidents per run | 0.00 ± 0.00 |
| Fault-free runs: false alarms | 1 of 285 windows (0.4%), 0 alerts |

| Scenario | Detected | Delay | Alert delay | Anomalies | Alerts | Worst severity |
|---|---|---|---|---|---|---|
| error_burst | 3/3 | 60 s ± 7 | 60 s ± 7 | 4.67 ± 1.15 | 1.67 ± 0.58 | critical 3 |
| latency_spike | 3/3 | 60 s ± 7 | 60 s ± 7 | 3.33 ± 1.15 | 1.33 ± 0.58 | high 3 |
| new_error | 3/3 | 40 s ± 28 | 40 s ± 28 | 5.67 ± 0.58 | 2.00 ± 0.00 | high 3 |
| silent_service | 3/3 | 40 s ± 27 | 40 s ± 27 | 8.67 ± 0.58 | 3.67 ± 0.58 | critical 3 |
| cascading_failure | 3/3 | 60 s ± 7 | 60 s ± 7 | 11.00 ± 1.73 | 4.00 ± 0.00 | critical 3 |
