# QScheduler-Swarming

QScheduler-Swarming is an implementation of the [ExternalScheduler](https://chromium.googlesource.com/infra/luci/luci-py/+/refs/heads/master/appengine/swarming/proto/api/plugin.proto) API for [swarming](https://chromium.googlesource.com/infra/luci/luci-py/+/refs/heads/master/appengine/swarming/), using the [quotascheduler](https://chromium.googlesource.com/infra/infra/+/refs/heads/master/go/src/infra/qscheduler/qslib/) algorithm.

This server used to be hosted on appengine, which explains why the code
is located in the appengine/* directory structure; however, it no longer runs on
appengine. It now runs on kubernetes.

Code layout:

- `api/`            Definitions for the Admin API to QScheduler-Swarming.
- `app/config`      Definitions for QScheduler-Swarming configuration.
- `app/eventlog`    BigQuery logging helper.
- `app/frontend`    Request handlers.
- `app/state`       Common code for mutating scheduler state, and request-batcher implementation.
- `app/state/metrics`       Time-series and analytics emission.
- `app/state/nodestore`     Datastore-backed store of scheduler state with in-memory cache, distributed over many write-only datastore entities.
- `app/state/operations`    State mutators for scheduling requests.
- `app/cmd`         Dockerfile and entry point for server.