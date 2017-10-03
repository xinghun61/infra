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

## Devserver

To run test-results locally:

```
make devserver
```

You can use the -F flag with curl to send multipart/form data. For example, to
send request to test `testfile/upload`:

```
curl -v -F master='tryserver.chromium.mac' -F builder='linux_chromium_rel_ng' -F
file=@<local-path-to-test-results-file> -F testtype='browser_tests (with patch)'
http://localhost:8080/testfile/upload
```

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

# How to upload test results to the Test Results Server

## Why?

A few services use test results from test launchers running on Chromium
Infrastructure to provide useful data for developers:

* [Flakiness Dashboard] allows to have a quick look at recent test runs to help
  the pattern of failures and platforms which are affected.
* [Chromium Try Flakes app] reports flaky tests on the bug tracker, e.g. see
  [issue 707664]. Without test results it can only file bugs for the whole step
  containing a flaky test, e.g. see [issue 707545].
* [Flakiness Surface], which is still in development, uses this data to show the
  tests that have highest flakiness and will in future provide detailed
  information about each specific test to help finding the root cause and fixing
  them.

## How?

You can start uploading your test results in 3 steps:

1. Read [JSON Test Results Format] spec.
1. Modify source code of your test launcher to make a request to the
   https://test-results.appspot.com/testfile/upload after running the tests and
   collecting their results. The request should be [multipart/form-data] POST
   request and include the following parameters:
   * master, e.g. `tryserver.chromium.linux` (note the missing `master.` prefix),
   * builder, e.g. `linux_chromium_rel_ng`,
   * testtype, e.g. `browser_tests (with patch)`, and
   * file, e.g. [this file][example-json-file] (but rename to remove the "_0"
     suffix).
1. Deploy the changes to production and verify that your test results are shown
   in Flakiness Dashboard after selecting test type that matches your step name.

Recommended way to implement this is to use [test\_results.upload function] in
the recipe that is running your test, e.g. see [example][recipe-upload-example].
However, if for some reasons you can not do that, you can also use this [example
in Python][python-upload-example].

If something is unclear, please let us know at infra-dev+flakiness@chromium.org
and we’ll use your feedback to improve this doc.

[Flakiness Dashboard]: https://test-results.appspot.com/dashboards/flakiness_dashboard.html#testType=interactive_ui_tests%20(with%20patch)&tests=WebViewInteractiveTests%2FWebViewDragDropInteractiveTest.DragDropWithinWebView%2F1
[Chromium Try Flakes app]: http://chromium-try-flakes.appspot.com/
[issue 707664]: https://bugs.chromium.org/p/chromium/issues/detail?id=707664
[issue 707545]: https://bugs.chromium.org/p/chromium/issues/detail?id=707545
[Flakiness Surface]: https://test-results.appspot.com/flakiness
[JSON Test Results Format]: https://www.chromium.org/developers/the-json-test-results-format
[multipart/form-data]: https://www.w3.org/TR/html401/interact/forms.html#h-17.13.4.2
[example-json-file]: ./frontend/testdata/full_results_0.json
[test\_results.upload function]: https://cs.chromium.org/chromium/build/scripts/slave/recipe_modules/test_results/api.py?l=11&rcl=4892db3bf1623b939c31f5929c139abec080c9a6
[recipe-upload-example]: https://cs.chromium.org/chromium/build/scripts/slave/recipe_modules/chromium_tests/steps.py?l=432&rcl=4892db3bf1623b939c31f5929c139abec080c9a6
[python-upload-example]: https://cs.chromium.org/chromium/build/scripts/slave/recipe_modules/test_results/resources/test_results_uploader.py?l=31&rcl=4892db3bf1623b939c31f5929c139abec080c9a6
