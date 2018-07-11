# depot\_tools monitoring app
This is a simple GAE app to collect the metrics uploaded by depot\_tools and
store them in BigQuery.
This app is only reachable when the *X-AppEngine-Trusted-IP-Request* header,
which is set only on requests received from corp machines, is present on the
request. This is a way to ensure we don't collect data from non-Googlers.

## API
This app exposes two endpoints:
- **/should-upload**

  Returns 200 if the request comes from a corp machine, and 403 otherwise.
- **/upload**

  Accepts a JSON file in the format described by `monitoring_logs_schema.json`
  and writes the data to the `depot_tools` table in the `metrics` dataset of the
  `cit-cli-metrics` project.

  It also returns 200 if the request comes from a corp machine (300 if there was
  an internal error), and 403 otherwise.

## Deployment
To deploy the app, run `gae.py upload`.

Adittionaly, there is a `schema2proto` Go script to transform the JSON schema to
a protobuf, so the schema can be updated via `bqschemaupdater`:
- `go run utils/schema2proto.go metrics/metrics_schema.json
  metrics/metrics_schema.proto`
- `bqschemaupdater -table cit-cli-metrics.metrics.depot_tools -message-dir
  metrics -message metrics.MetricsSchema`



