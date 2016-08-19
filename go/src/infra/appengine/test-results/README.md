# test-results

This is the Go module for the test-results server (https://test-results.appspot.com).
Remaining parts are in the default Python module located at `infra/appengine/test_results`.
Each handler will eventually be migrated from the Python application to Go.

For the list of paths handled by the Go module, see
`frontend/app.yaml` and `dispatch.yaml`.

For more details, see the README at `infra/appengine/test_results`.

## Test

```
go test -race ./...
```

## Deploy

```
appcfg.py -A test-results-hrd -V $VERSION update frontend/app.yaml
```

Then migrate traffic to the new version.

If necessary, also update `dispatch.yaml`, `queue.yaml`, etc.

```
appcfg.py -A test-results-hrd -V $VERSION update_dispatch .
```
