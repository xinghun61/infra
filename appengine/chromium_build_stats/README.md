This is an application designed to collect and analyze build/compile stats.

Deign Doc: [Chromium build time profiler](https://docs.google.com/a/chromium.org/document/d/16TdPTIIZbtAarXZIMJdiT9CePG5WYCrdxm5u9UuHXNY/edit#heading=h.xgjl2srtytjt)

default module
 in default/ dir

How to:

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
  $ ./goenv.sh goapp deploy default
 (or
  $ cd default; ../goenv.sh goapp deploy
 )

 to run gofmt
  $ cd default; ../goenv.sh goapp fmt

  $ goenv.sh goapp fmt chromegomalog ninjalog

 to run govet
  $ cd default; ../goenv.sh goapp vet

  $ goenv.sh goapp vet chromegomalog ninjalog

 to run test
  $ cd default; ../goenv.sh goapp test

 to read go documentation

  $ ./goenv.sh godoc <package>
  $ ./goenv.sh godoc <package> <symbol>
 (or
  $ ./goenv.sh godoc -http :6060
 and go to http://localhost:6060
 )
