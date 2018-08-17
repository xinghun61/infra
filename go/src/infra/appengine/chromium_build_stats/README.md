# This is an application designed to collect and analyze build/compile stats.

Deign Doc: [Chromium build time profiler](https://docs.google.com/a/chromium.org/document/d/16TdPTIIZbtAarXZIMJdiT9CePG5WYCrdxm5u9UuHXNY/edit#heading=h.xgjl2srtytjt)

How to:

See [infra/go/README.md](../../../../README.md) for preparation.

 to re-generate trace-viewer contents
  $ <CHROMIUM_SRC>/third_party/catapult/tracing/bin/trace2html /dev/null --output=tmpl/trace-viewer.html

 to compile
   $ make build

 to run locally with dev_appserver
 (note: no service account available, so you couldn't
  fetch file from gs://chrome-goma-log)
   $ dev_appserver.py app.yaml

 to deploy to production
  $ make deploy_prod

 and need to [migrate traffic](https://cloud.google.com/appengine/docs/standard/go/migrating-traffic).

 NOTE: Check ninja trace data after deploy. If it's not accessible,
 you must forget to generate trace-viewer contents (See the first item of
 this how-to). Re-generate it and deploy again.

 to run test
  $ make test

 to read go documentation

  $ godoc <package>
  $ godoc <package> <symbol>
 (or
  $ godoc -http :6060
 and go to http://localhost:6060
 )
