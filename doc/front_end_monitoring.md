# Front-end Monitoring How-To

You can use ts-mon.js to instrument your front-end code, view metrics in your
dashboards, and set up alerts based on those metrics. This document shows
you how to set up ts_mon monitoring on the front-end.

## Installation and Setup

The front-end library lives at
[crdx/chopsui/tsmon-client.js](../crdx/chopsui/tsmon-client.js). Import it
on your page to get started. The easiest way is to symlink in the `chopsui`
directory and serve it.

```html
<script
  type="module"
  async
  src="path/to/chopsui/tsmon-client.js">
</script>
```

Next, in your JS, instantiate the client and register a metric. You can add
additional metric fields, for example a `status` field for XHR response status.

```js
const tsMon = new window.chops.tsmon.TSMonClient();

// An object of metric metadata.
const metricMetaData = {};
// A Map of metric fields.
const metricFields = new Map([
  ['status', TSMonClient.intField('status')],
]);
const metric = tsMon.cumulativeDistribution(
  'yourapp/frontend/rutabaga_load_latency',
  'Latency for loading rutabagas.',
  metricMetaData, metricFields,
);
```

You'll also need to set up the server-side proxy handler. For Python, subclass
the handler like this:

```python
from gae_ts_mon.handlers import TSMonJSHandler


# For now, metrics need to be declared twice, once client side and once server side.
RUTABAGA_LATENCY_METRIC = ts_mon.CumulativeDistributionMetric(
  'yourapp/frontend/rutabaga_load_latency',
  'Latency for loading rutabagas.',
  units=ts_mon.MetricsDataUnits.MILLISECONDS,
  field_spec=[ts_mon.IntegerField('status')])


class YourAppTSMonJSHandler(TSMonJSHandler):

  def __init__(self, request=None, response=None):
    super(YourAppTSMonJSHandler, self).__init__(request, response)
    self.register_metrics([RUTABAGA_LATENCY_METRIC])

  def xsrf_is_valid(self, _body):
    # Do your own XSRF checking here.
    return True
```

> Note: the Go server-side proxy handler is not yet available.

## Sending Measurements

Then in JavaScript when something comes up that you want to measure:

```js
const elapsedMs = new Date().getTime() - startTime;

const metricFields = new Map([
  ['status', <compute the value>],
]);
metric.add(elapsedMs, metricFields);
```

Metrics are flushed automatically by the JS handler every 60 seconds.

The types of metrics you can measure are the same as the back-end ts_mon library.
See [crdx/chopsui/tsmon-client.js](../crdx/chopsui/tsmon-client.js) for more
details.
