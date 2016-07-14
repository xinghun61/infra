# test-results

This is a Go port of the test-results server, currently a Python application located at
`infra/appengine/test_results`. Each handler will eventually be migrated from the Python
application to Go.

For more details, see the README at `infra/appengine/test_results`.

## Test

```
go test -race ./...
```

