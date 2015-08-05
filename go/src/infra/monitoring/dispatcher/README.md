# Alerts Dispatcher
This application generates alerts displayed on
[Sheriff-o-Matic](sheriff-o-matic.appspot.com).

## Running in Production

Alerts dispatcher runs every 10 minutes on [infra.cron](https://build.chromium.org/p/chromium.infra.cron/builders/alerts-dispatcher)

Each run polls builders etc every 60s and analyzes results to generate alerts,
which are then posted to 
sheriff-o-matic.appspot.com/api/v1/alerts/[various trees]


The recipe is in 
[tools/build_limited/scripts/slave/recipes/infra/alerts_dispatcher.py](https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave.git/+/master/recipes/infra/alerts_dispatcher.py)

### Deploying a New Build

Alerts dispatcher uses CIPD to deploy new packages. Step one is to build a new
package (from infra/build):

```
./build.py dispatcher --upload
```

Successful build output will tell you something like:

```
--------------------------------------------------------------------------------
Summary
--------------------------------------------------------------------------------
infra/monitoring/dispatcher/linux-amd64 2d2f91e467892b53b3cd5a1c1845b7fa1fd78948
```

Edit alerts_dispatcher.py's pkgs var to use this hash for the "version"
property.

Send the CL out for review, and once it's submitted it should be picked up by
infra.cron within the next 10 minutes.

## Running Locally
From infra/go:

```
eval `./env.py` # skip this if you've run it already.
go build infra/monitoring/dispatcher
./dispatcher -tree=chromium
```

By default, dispatcher will write its output to a local alerts.json file.  If
you want to run it against a sheriff-o-matic instance, you should set the
target URL with the -base-url= flag (make it 
localhost:8080/api/v1/alerts for a local SoM instance, e.g.). Dispatcher
will post a separate json alerts object for each tree to (base-url)/tree.

Other useful flags for debugging purposes, which can progressively narrow the
scope of analysis (and thus lower run time and less noisy logging/output):

 * -trees= (comma separated list) will only check builds for those trees
 * -master= will only scan builds from that master
 * -builder= will only scan that builder
 * -build= will only scan a particular build number

### Debugging with Snapshots

Alerts dispatcher can grab the state of the build system at the current point
in time, so you can replay it again without hitting the network.  This is
really handy for reproducing alerting bugs that depend on the current state
of the system.

To test out a change quickly or repeatably, use the -record-snapshot and
-replay-snapshot flags.

Record: Run dispatcher once with -record-snapshot=/some/dir
to record all of the responses it gets from the network to local disk.

Replay: Run dispatcher again with -replay-snapshot=/some/dir and it will read
all of the previously recorded responses from disk rather than the network.


