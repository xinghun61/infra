Our event pipeline collects, stores, and aggregates event data from ChOps
services. Event data can be any piece of information we want to collect for
analysis or tracking. It is distinct from timeseries data, for which we use
[tsmon](https://chrome-internal.googlesource.com/infra/infra_internal/+/master/doc/ts_mon.md).

# Creating a new BigQuery table

Table definitions are stored in infra.git in a subdirectory of
`go/src/infra/tools/bqschemaupdater` and added/updated with the
[bqschemaupdater](../go/src/infra/tools/bqschemaupdater/README.md) tool.

bqschemaupdater takes a JSON version of the
[TableDef
proto](../../go/src/infra/libs/bqschema/tabledef/table_def.proto)

You need to be authenticated in the chrome-infra-events project to be able to
create a new table. To check your authentication status, ensure that you have
the Cloud SDK [installed](https://cloud.google.com/sdk/docs/quickstarts), then
run:

```
gcloud info
```

If you don't see: `Project: [chrome-infra-events]`, reach out to an
[editor](https://pantheon.corp.google.com/iam-admin/iam/project?project=chrome-infra-events&organizationId=433637338589)
to request access.

To create a new BigQuery table:

```
cd go/src/infra/tools/bqschemaupdater  # In infra.git
touch <dataset-subdirectory>/<table-id>.json
# Reference tabledef/table_def.proto for message format
go build
./bqschemaupdater --dryrun <dataset-subdirectory>/<table-id>.json
# Looks good? Create CL for review... Review... Commit...
# Actually create the table
./bqshemaupdater <dataset-subdirectory>/<table-id>.json
```

## Go struct export

The [bqexport](../../go/src/infra/cmd/bqexport) tool is a Go generator utility
that can generate `bqschemaupdater`-compatible table definitions from BigQuery
Go structs. See [bqexport documentation](../../go/src/infra/cmd/bqexport) for
more information.

# Sending events

Once you have a table, you can send events to it!

## Credentials

You need to ensure the machines that will be running the code which sends events
have proper credentials. At this point, you may need to enlist the help of a
Chrome Operations Googler, as many of the following resources and repos are
internal.

1. Choose a [service
   account](https://cloud.google.com/docs/authentication/#service_accounts).
   This account may be a service account that is already associated with the
   service, or it may be a new one that you create.
1. Give that service account the "BigQuery Data Editor" IAM role using the
   [cloud console](https://console.cloud.google.com) under "IAM & Admin" >>
   "IAM" in the `chrome-infra-events` project. You'll need the proper privileges
   to do this. If you don't have them, ask a Chrome Infrastructure team member
   for help.
1. If you have created a new private key for an account, you'll need to add it
   to puppet. [More
   info.](https://chrome-internal.googlesource.com/infra/puppet/+/master/README.md)
1. Make sure that file is available to your service. For CQ, this takes the form
   of passing the name of the credentials file to the service on start. [See
   CL.](https://chrome-internal-review.googlesource.com/c/405268/)

## From Python

### Dependencies

You will need the
[google-cloud-bigquery](https://pypi.python.org/pypi/google-cloud-bigquery)
library in your environment. infra.git/ENV has this dependency already, so you
only need to add it if you are working outside that environment.

### Example

See
[this change](https://chrome-internal-review.googlesource.com/c/407748/)
for a simple example. (TODO: replace with a non-internal example that uses
insertIDs.) The [API
docs](https://googlecloudplatform.github.io/google-cloud-python/stable/bigquery-usage.html)
can also be helpful.

# Writing a Dataflow workflow

## Recommended Reading

The [beam documentation](https://beam.apache.org/documentation/) is a great
place to get started.

## Specifics for Chrome Infrastructure Workflows

Workflows are in the `packages/dataflow` directory. `packages/dataflow/common`
contains abstractions that you will likely want to use. Take a look at what is
available there before beginning your workflow.

## Development

See the [dataflow package
README](https://chromium.googlesource.com/infra/infra/+/master/packages/dataflow/)
for more information.

## Testing

You should write tests for your pipeline. Tests can be run using test.py, e.g.
`./test.py test packages/dataflow`.

# Scheduling a Dataflow workflow

We want Dataflow workflows like the ones that populate our aggregate tables
(e.g. cq_attempts) to run at regular intervals. You can accomplish this by
configuring a builder to run the
[remote_execute_dataflow_workflow recipe](https://chromium.googlesource.com/infra/infra/+/master/recipes/recipes/remote_execute_dataflow_workflow.py)
with the proper properties. See [this
change](https://chrome-internal-review.googlesource.com/c/412934/) for an
example.
