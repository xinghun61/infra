# sheriff-o-matic

aka SoM

## Requirements

You'll need some extras that aren't in the default infra checkout.

```sh
# sudo where appropriate for your setup.

apt-get install nodejs
apt-get install npm
npm install -g bower
npm install -g web-component-tester
npm install -g web-component-tester-istanbul
```

## Getting up and running

After initial checkout, make sure you have all of the bower dependencies
installed. Also run this whenever bower.json is updated:

```sh
bower install

# Same with npm and packages.json:
npm install
```

To run locally from an infra.git checkout:
```sh
./gae.py devserver
```

To run tests:
```sh
# For go:
go test

# For JS:
xvfb-run -a wct
```

To view test coverage report after running tests:
```sh
google-chrome ./coverage/lcov-report/index.html
```

To deploy:
```sh
make deploy
```

## Configuring and populating devserver SoM with alerts

Once you have a server running locally, you'll want to add at least one
tree configuration to the datastore. Make sure you are logged in locally
as an admin user (admin checkbox on fake devserver login page).

Navigate to `http://localhost:8080/admin/settings` and fill out the tree(s)
you wish to test with locally.

After you have at least one tree configured, you'll want to populate your
local SoM using alerts-dispatcher. From `infra/go` in your checkout,
run the following to generate alerts for the chromium tree:

```sh
go build infra/monitoring/dispatcher
./dispatcher --gatekeeper=../../build/scripts/slave/gatekeeper.json --gatekeeper-trees=../../build/scripts/slave/gatekeeper_trees.json --trees=chromium --base-url http://localhost:8080/api/v1/alerts
```

See [alerts-dispatcher's README](https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/monitoring/dispatcher/) for more information about using this tool.

## Testing the bug queue locally
Testing the bug queue locally requires access to Monorail production. To do
this, you will need to get credentials for a, App Engine service account.

* Navigate to Google Cloud console -> IAM & Admin -> Service accounts.
* Select the three-dot menu on the "App Engine default service account" item and
click "Create Key".
* Select the "JSON" option from the radio buttons and then click the "Create" button.
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
