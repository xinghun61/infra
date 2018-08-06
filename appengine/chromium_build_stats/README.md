This is an application designed to collect and analyze build/compile stats.

Deign Doc: [Chromium build time profiler](https://docs.google.com/a/chromium.org/document/d/16TdPTIIZbtAarXZIMJdiT9CePG5WYCrdxm5u9UuHXNY/edit#heading=h.xgjl2srtytjt)

default module
 in default/ dir

How to:

 to re-generate trace-viewer contents
  $ cd default; <CHROMIUM_SRC>/third_party/catapult/tracing/bin/trace2html tmpl/dummy.json --output=tmpl/trace-viewer.html

 to compile
   $ cd default; ../goenv.sh goapp build

 to run locally with dev_appserver
 (note: no service account available, so you couldn't
  fetch file from gs://chrome-goma-log)
   $ ./goenv.sh goapp serve default
 (or
   $ cd default; ../goenv.sh goapp serve
 )

 to deploy to production
  $ ./goenv.sh goapp deploy --version $version default
 (or
  $ cd default; ../goenv.sh goapp deploy --version $version
 )
 version would be $(git log -1 --pretty=format:git-%H)

 and need to [migrate traffic](https://cloud.google.com/appengine/docs/standard/go/migrating-traffic).

 NOTE: Check ninja trace data after deploy. If it's not accessible,
 you must forget to generate trace-viewer contents (See the first item of
 this how-to). Re-generate it and deploy again.

 to run gofmt
  $ cd default; ../goenv.sh goapp fmt

  $ goenv.sh goapp fmt logstore ninjalog

 to run govet
  $ cd default; ../goenv.sh goapp vet

  $ goenv.sh goapp vet logstore ninjalog

 to run test
  $ cd default; ../goenv.sh goapp test

 to read go documentation

  $ ./goenv.sh godoc <package>
  $ ./goenv.sh godoc <package> <symbol>
 (or
  $ ./goenv.sh godoc -http :6060
 and go to http://localhost:6060
 )
