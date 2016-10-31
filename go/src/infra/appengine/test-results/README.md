# test-results

This is the Go module for the test-results server
(https://test-results.appspot.com). Remaining parts are in the default Python
module located at `infra/appengine/test_results`. Each handler will eventually
be migrated from the Python application to Go.

For the list of paths handled by the Go module, see `frontend/app.yaml` and
`dispatch.yaml`.

For more details, see the README at `infra/appengine/test_results`.

## Prerequisites

```
apt-get install nodejs
apt-get install npm
npm install -g bower
npm install -g vulcanize
```

Google employees should follow instructions at http://go/nodejs to install
NodeJS 4.x or later.

## Build

```
make build
```

This can be useful if you want to debug a vulcanized file containing combined
and compressed source of all used components. This is actual code used in
production. Note that this should not be used for normal development on a local
devserver since changes to source code of the components will not be result in
changes in the tested app. To go back to normal development, please run

```
make clean
```

## Test

```
make test
```

## Deploy

```
make [deploy_staging|deploy_prod|deploy_cron|deploy_dispatch|deploy_queues]
```

Then migrate traffic to the new version.
