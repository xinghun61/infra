# sheriff-o-matic

aka SoM

## Prerequisites

Download and install the [AppEngine SDK for Go](https://cloud.google.com/appengine/docs/flexible/go/download).

You will need a chrome infra checkout as
[described here](https://chromium.googlesource.com/infra/infra/). That will
create a local checkout of the entire infra repo, but that will include this
application and many of its dependencies.

Warning: If you are starting from scratch, there may be a lot more setup involved
than you expected. Please bear with us.

You'll also need some extras that aren't in the default infra checkout.

```sh
# sudo where appropriate for your setup.

npm install -g bower
```

If you don't have npm or node installed yet, make sure you do so using
`gclient runhooks` to pick up infra's CIPD packages for nodejs and
npm (avoid using other installation methods, as they won't match what
the builders and other infra devs have installed). *Then* make sure you've
run
```
eval `../../../../env.py`
```
in that shell window.

## Getting up and running locally

After initial checkout, make sure you have all of the bower dependencies
installed. Also run this whenever bower.json is updated:

```sh
cd frontend
make deps
```

(Note that you should always be able to `rm -rf fronted/bower_components`
and re-run `bower install` at any time. Occasionally there are changes that,
when applied over an existing `frontend/bower_components`, will b0rk your
checkout.)

To run locally from an infra.git checkout:
```sh
make devserver
```

To run tests:
```sh
# For go:
cd som
go test

# For JS:
cd frontend
xvfb-run -a wct
```

To view test coverage report after running tests:
```sh
google-chrome ./coverage/lcov-report/index.html
```
## Access to AppEngine instances

If you would like to test your changes on our staging server (this is often
necessary in order to test and debug integrations, and some issues will
only reliably reproduce in the actual GAE runtime rather than local devserver),
please contact cit-sheriffing@google.com to request access. We're happy to
grant staging access to contributors!

## Deploying a new release

First create a new CL for the RELNOTES.md update. Then run:
```sh
make relnotes
```

Note that you may need to install `GOOGLE_APPLICATION_CREDENTIALS` as
described below in order to have relnotes work properly this way.

Copy and paste the output into the top of `README.md` and make any manual edits
if necessary. You can also use the optional flags `-since-date YYYY-MM-DD` or
`-since-hash=<git short hash>` if you need to manually specify the range
of commits to include. Then:

- Send the RELNOTES.md update CL for review by OWNERS.
- Land CL.
- run `make deploy_prod`
- Go to the Versions section of the
[App Engine Console](https://appengine.google.com/) and update the default
version of the app services. *Rembember to update both the "default" and "analyzer"
services*. Having the default and analyzer services running different versions
may cause errors and/or monitoring alerts to fire.
- Send a PSA email to cit-sheriffing@ about the new release.

### Deploying to staging

Sheriff-o-Matic also has a staging server with the AppEngine ID
sheriff-o-matic-staging. To deploy to staging:

- run `make deploy_staging`
- Optional: Go to the Versions section of the
[App Engine Console](https://appengine.google.com/) and update the default
version of the app.

### Authenticating for deployment

In order to deploy to App Engine, you will need to be a member of the
project (either sheriff-o-matic or sheriff-o-matic-staging). Before your first
deployment, you will have to run `./gae.py login` to authenticate yourself.

## Configuring and populating devserver SoM with alerts

Once you have a server running locally, you'll want to add at least one
tree configuration to the datastore. Make sure you are logged in locally
as an admin user (admin checkbox on fake devserver login page).

Navigate to [localhost:8080/admin/settings](http://localhost:8080/admin/settings)
and fill out the tree(s) you wish to test with locally. For consistency, you
may just want to copy the [settings from prod](http://sheriff-o-matic.appspot.com/admin/settings).

If you don't have access to prod or staging, you can manually enter this for
"Trees in SOM" to get started with a reasonable default:

```
android:Android,chromeos:Chrome OS,chromium:Chromium,chromium.perf:Chromium Perf,gardener:ChromeOS Gardener,ios:iOS,trooper:Trooper
```

After you have at least one tree configured, you'll want to populate your
local SoM using either local cron tasks or alerts-dispatcher.

### Populating alerts from local cron tasks (any tree besides Chrome OS):
You can use local cron anaylzers and skip all of this by navigating to e.g.
[http://localhost:8081/_cron/analyze/chromium](http://localhost:8081/_cron/analyze/chromium).
You can replace `chromium` in `_cron/analyze/chromium` with the name of whichever tree you
wish to analyze. Note that the cron analyzers run on a different port than the
UI (8081 vs 8080). This is because the cron tasks run in a separate GAE service
(aka "module" in some docs). These requests may also take quite a while to
complete, depending on the current state of your builders.

### CrOS: Populating alerts from a local alerts-dispatcher run

ChromeOS has a separate som_alerts_dispatcher process for scanning builds and
generating alerts, which is a special case unlike the rest of the trees on SoM.
This code lives [here](https://cs.chromium.org/chromium/src/third_party/chromite/scripts/som_alerts_dispatcher.py).
Please consult the source or recent comitters for instructions on how to use or modify it.

### Populating alerts from a JSON file

In some instances, you may want to input specific alert JSON data into
Sheriff-o-Matic. For example, you may wish to send a JSON file containing a
snapshot of old alerts, or you may wish to tailor JSON data for a specific case
you are testing.

To do this, you can use curl to directly post alerts to Sheriff-o-Matic. For
example, the following command would post the contents of a JSON file
containing alert data to the chromium tree.

```sh
curl -X POST -d @/path/to/alerts.json localhost:8080/api/v1/alerts/chromium
```

An example of the alerts JSON format used by Sheriff-o-Matic can be found at
test/alerts-data.js

For more detailed information on the alert JSON format, see
[infra/monitoring/messages.Alert](https://cs.chromium.org/chromium/infra/go/src/infra/monitoring/messages/alerts.go)

## Setting up credentials for local testing

You will need access to either staging or prod
sheriff-o-matic before you can do this, so contact cit-sheriffing@google.com
to request access if don't already have it.

Currently, Sheriff-o-Matic accesses two APIs that require service account credentials:

* Monorail - for the bug queue
* Google Cloud Storage - for secure storage of the tree logo images

To test these features locally you will need to get credentials for an App
Engine service account.

* Navigate to Google Cloud console -> IAM & Admin -> Service accounts.
* Select the three-dot menu on the "App Engine default service account" item and
click "Create Key".
* Select the "JSON" option from the radio buttons and then click the "Create"
button.
* A JSON file containing your key will download.

Once you have the key for your service account, add the key to your environment
variables:

```sh
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials/file.json
```

## Contributors

We don't currently run the `WCT` tests on CQ. So *please* be sure to run them
yourself before submitting. Also keep an eye on test coverage as you make
changes. It should not decrease with new commits.
