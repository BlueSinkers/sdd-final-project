# Monitoring and the SLO

## What we log

Each service writes exactly one line to standard output for every HTTP request it handles:

```
service=swaps method=POST path=/swaps status=201 duration_ms=13.2
```

`duration_ms` is the time the service spent on the request, measured in the request
middleware (`app/main.py`). Uvicorn's own access log is switched off in the image so there is
one line per request, not two. The path is percent-encoded in the line, so a crafted URL
cannot inject a fake request line. A browser's CORS preflight (`OPTIONS`) is answered by the
CORS layer before it reaches the service and is not logged. Startup, migrations, database
retries and errors are logged as ordinary lines; a stack trace goes to the log and never to
the caller.

On Azure, Container Apps sends everything written to standard output to the Log Analytics
workspace created by `infra/setup.sh`. The lines land in the table
`ContainerAppConsoleLogs_CL`, with the text in `Log_s` and the app name in
`ContainerAppName_s`. New lines show up after one to five minutes.

## Queries

All queries are in [`infra/monitoring/`](../infra/monitoring/). Open the workspace in the
Azure portal, choose **Logs**, paste a query and run it.

| File | Answers |
|---|---|
| `requests.kql` | The parsed request rows, as a starting point for any new question |
| `request_count.kql` | How many requests does each service get? |
| `error_rate.kql` | What share of requests fail on our side (5xx)? |
| `response_time.kql` | How fast are we: p50, p95, p99? |
| `slo_swaps.kql` | Did we meet the SLO over the last 7 days, and how much error budget is left? |
| `slo_swaps_daily.kql` | On which days was the SLO missed? |
| `slowest_and_failing.kql` | Which endpoints are slow or failing? |
| `startup_and_errors.kql` | What happened at startup, and what errors were logged? |

A 4xx answer (a validation error, an unknown id) is the caller's mistake and does not count
as an error. Requests to `/health` are left out of the charts so the deploy pipeline's health
check does not inflate the numbers.

## Dashboard

[`infra/monitoring/workbook.json`](../infra/monitoring/workbook.json) is an Azure Monitor
workbook with the SLO result at the top, then request count, error rate and response time per
service, the SLO per day, and a table of endpoints.

To install it: Azure portal > the Log Analytics workspace > **Workbooks** > **New** > the
**Advanced Editor** button (`</>`) > paste the file's contents > **Apply** > **Save**. Pick the
time range with the pills at the top.

**Installed in our resource group** as a shared workbook named **Thrift-Swap Board**
(resource id ends with `.../microsoft.insights/workbooks/615b97fb-b841-444d-a23b-de5f6dc969b0`).
Open it from: Azure portal > resource group `rg-sdd-3b-g1` > the workbook, or from the
`sdd-3b-g1-logs` workspace > **Workbooks**.

## Observations from production (2026-11-24)

Ran each query in `infra/monitoring/` against the real `sdd-3b-g1-logs` workspace after the
first go-live (commit `dfe9083…`). Numbers below are from Log Analytics for the last ~24 hours
unless noted. Traffic is still light (smoke test + manual checks), so treat this as a first
baseline, not a full week of SLO evidence.

| Check | Result |
|---|---|
| Logs arriving | Yes. Both Container Apps write to `ContainerAppConsoleLogs_CL`. |
| Log line parse | Yes. Lines match `service=… method=… path=… status=… duration_ms=…`. |
| Request count (excl. `/health`) | listings 22, swaps 22 |
| 5xx error rate | 0% on both services |
| 4xx (caller errors) | listings 2, swaps 1 (validation / unknown id from smoke tests) |
| Response time (excl. `/health`) | listings p50 8.1 ms, p95 58.1 ms, p99 101.8 ms; swaps p50 4.5 ms, p95 60.8 ms, p99 75.5 ms |
| SLO (`POST /swaps`, 7 days) | **met** — 2 of 2 good (100%), p50 6.7 ms, p99 18.6 ms; error budget 0 because volume is still tiny |
| Workbook | Installed and linked to `sdd-3b-g1-logs` |

Busiest endpoints so far: `GET /listings` and `GET /swaps` (browse). `POST /swaps` only has
the smoke-test volume; re-check `slo_swaps.kql` after the Sprint Review demo when there is
more traffic.

## The SLO

> **99% of `POST /swaps` requests complete in under 500 ms, measured over 7 days.**

- **Why this request:** proposing a swap is the feature beyond CRUD; it is the one request a
  user waits on to learn something.
- **Indicator:** from the request log line, the share of `POST /swaps` requests with
  `duration_ms < 500` and a status below 500.
- **Measured by:** `slo_swaps.kql`, which also reports the error budget. At 99%, 1 in 100
  requests may be slow or fail; with 1,000 proposals in a week that is 10 requests.
- **What it does not cover:** the time a request waits before it reaches the service. Both
  Container Apps scale to zero, so the first request after an idle period waits for a
  container to start, and that wait is not in `duration_ms`. We chose this on purpose and
  wrote down why in ADR-6 ([`decisions.md`](decisions.md)).

### The log line is a contract

Every query parses the one log line each service writes. `listings/tests/test_log_contract.py`
and `swaps/tests/test_log_contract.py` read the `parse` expression out of the `.kql` files
and require the services' real log line to match it, so renaming a field on either side fails
CI instead of silently emptying the dashboard. They prove the shape matches; they do not prove
it in Azure, so run each query once on real logs after the first deploy.

### Alerting (not set up)

The dashboard shows the SLO but nothing tells anyone when it slips. After the first deploy,
the simplest alert is a scheduled-query alert rule on `slo_swaps.kql` (Azure portal > the Log
Analytics workspace > **Alerts** > **Create** > **Alert rule**, condition `slo_met` is false,
evaluated hourly). It is not created by `infra/setup.sh` because we could not test that
command without an Azure account.

### If the SLO is at risk

1. Run `slowest_and_failing.kql`: is it slowness or errors, and on which endpoint?
2. Run `startup_and_errors.kql`: database retries mean the database was resuming from a
   pause; a stack trace means a bug.
3. If a deploy caused it, roll back (see [`deploy.md`](deploy.md)).
4. If the error budget for the week is gone, stop shipping features and fix reliability first.

## Producing traffic and a second opinion

`tools/latency_check.py` sends `POST /swaps` requests one after another and prints the
percentiles and the share under 500 ms, measured from the caller's side (so it includes the
network and any cold start):

```bash
python tools/latency_check.py                        # local compose stack, 200 requests
python tools/latency_check.py https://<swaps-app>    # the deployed service
```

Measured locally on 23 Nov 2026 (service run from source on a laptop, SQL Server 2022 in
Docker, 300 requests): p50 16 ms, p95 27 ms, p99 50 ms, max 187 ms, 300 of 300 under 500 ms.
Local numbers only show the code is nowhere near the limit; the SLO itself is judged on the
deployed service with `slo_swaps.kql`.
