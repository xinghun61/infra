# Monorail Issue Tracker

Monorail is the Issue Tracker used by the Chromium project and other related
projects. It is hosted at [bugs.chromium.org](https://bugs.chromium.org).

If you wish to file a bug against Monorail itself, please do so in our
[self-hosting tracker](https://bugs.chromium.org/p/monorail/issues/entry).
We also discuss development of Monorail at `infra-dev@chromium.org`.

## Testing

In order to run all of the Monorail unit tests, run `make test` in this
directory. If you wish to run just a subset of the tests, you can invoke the
test runner directly and give it a subdirectory: `../../test.py
appengine/monorail/tracker`.

## Running Locally

To run the app locally, you need to have a local MySQL database. Install MySQL
according to the canonical instructions for your platform. Then create
a new database an import our schema:

    mysql> create database monorail;
    mysql> use monorail;
    mysql> source /path/to/infra/appengine/monorail/schema/framework.sql;
    mysql> source /path/to/infra/appengine/monorail/schema/project.sql;
    mysql> source /path/to/infra/appengine/monorail/schema/tracker.sql;
    mysql> exit;

Then you can run the development server locally with just `make serve`.

## Deploying

The `app.yaml` and `Makefile` files contained in this directory point at the
official instances of Monorail maintained by the Chromium Infrastructure Team.
If you wish (and have sufficient permissions) to deploy to one of those, simply
run `make deploy_staging` or `make deploy_prod`. If you wish to set up your
own instance, edit the first line of the `app.yaml` and use gae.py directly,
or edit the `Makefile` to add an entry for your AppEngine app ID. It is likely
that you'll also want to edit many of the values in `settings.py`, which
specify debug email addresses, instance counts, and default Google Storage
buckets.
