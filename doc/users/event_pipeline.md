# Overview

Our event pipeline collects, stores, and aggregates event data from ChOps
services. Event data can be any piece of information we want to collect for
analysis or tracking. It is distinct from timeseries data, for which we use
[tsmon](https://chrome-internal.googlesource.com/infra/infra_internal/+/master/doc/ts_mon.md).

See [katthomas's 2017 Opstoberfest
presentation](https://docs.google.com/a/google.com/presentation/d/11DoVXM5hrmSk9pgrj2vjQNd5ihr2_9dKtPYewPbLpjA/edit?usp=sharing)
for an overview of the components of the pipeline, with pictures!

# Step 1: Create a BigQuery table

## Table Organization

Tables are commonly identified by `<project-id>.<dataset_id>.<table_id>`.

BigQuery tables belong to datasets. Dataset IDs and table IDs should be
underscore delimited, e.g. `test_results`.

For Google Cloud Projects, tables should be created in their own project, under
the dataset "events."

Other projects can use the chrome-infra-events project id and create a dataset
specific to the team, product, or service. For example, CQ events are store in
`chrome-infra-events.cq.raw_events`.  In either case, table names are up to the
owner's discretion.

Datasets can be created in the easy-to-use [console](bigquery.cloud.google.com).

Rationale for per-project tables:

* Each project may ACL its tables as it sees fit, and apply its own quota
constraints to stay within budget.
* Different GCP instances of the same application code (say, staging vs
production for a given AppEngine app) may keep separate ACLs and retention
policies for their logs so they don’t write over each other.

## Creating and updating tables

Tables are defined by schemas. Schemas are stored in .proto form. Therefore we
have version control and can use the protoc tool to create language-specific
instances. Use the
[bqschemaupdater](https://chromium.googlesource.com/infra/luci/luci-go/+/master/tools/cmd/bqschemaupdater/README.md)
to create new tables or modify existing tables in BigQuery. As of right now,
this tool must be run manually.

# Step 2: Send events to BigQuery

Once you have a table, you can send events to it!

## Credentials

The following applies to non-GCP projects. Events sent from GCP projects to
tables owned by the same project should just work.

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

## How to Choose a Library

### TLDR

Go: use
[eventupload](https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/libs/eventupload)
[example CL](https://chromium-review.googlesource.com/c/infra/infra/+/719962)

Python: use
[BigQueryHelper](https://cs.chromium.org/chromium/infra/infra/libs/bigquery/helper.py?q=Bigqueryhelper&sq=package:chromium&l=11)
[example CL](https://chrome-internal-review.googlesource.com/c/infra/infra_internal/+/445955)


### Options

How you instrument your code to add event logging depends on your needs, and
there are a couple of options.

_We strongly advise against using the raw Google Cloud APIs for BigQuery because
they have some rough edges and failure modes that our chrome infra libs address
for you._

If you don’t need transactional integrity, and prefer a simpler configuration,
use the client library in [infra/libs/eventupload](https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/libs/eventupload).  This should be your default
choice if you’re just starting out.

If you need ~8ms latency on inserts, or transactional integrity with datastore
operations, use
[bqlog](https://cs.chromium.org/chromium/infra/go/src/go.chromium.org/luci/tokenserver/appengine/impl/utils/bqlog/bqlog.go) [TODO: update this link if/when bqlog moves out of
tokenserver into a shared location].

Design trade-offs for using infra/libs/eventupload instead of bqlog: lower
accuracy and precision. Some events may be duplicated in logs (say, if an
operation that logs events has to be retried due to datastore contention).
Intermittent failures in other supporting infrastructure may also cause events
to be lost.

Design trade-offs for using bqlog instead of eventupload: You will have to
enable task queues in your app if you haven’t already, and add a new cron task
to your configuration. You will also not be able to use the bqschemaupdater
(described below) tool to manage your logging schema code generation.

### From Go: eventupload

[eventuploader](https://godoc.org/chromium.googlesource.com/infra/infra.git/go/src/infra/libs/eventupload)
takes care of some boilerplate and makes it easy to add monitoring for uploads.
It also takes care of adding insert IDs, which BigQuery uses to deduplicate
rows. If you are not using `eventuploader`, check out
[insertid](https://codesearch.chromium.org/chromium/infra/go/src/infra/libs/eventupload/insertid.go?q=insertid.go&sq=package:chromium&l=1).

With `eventuploader`, you can construct a synchronous `Uploader` or asynchronous
`BatchUploader` depending on your needs.

[kitchen](../../go/src/infra/tools/kitchen/monitoring.go) is an example of a
tool that uses eventuploader.

### From Python: BigQueryHelper

You will need the
[google-cloud-bigquery](https://pypi.python.org/pypi/google-cloud-bigquery)
library in your environment. infra.git/ENV has this dependency already, so you
only need to add it if you are working outside that environment.

Check out the (../../infra/libs/bigquery/helper.py)[BigQueryHelper] class. It
makes it easy to add insert IDs, which BigQuery uses to deduplicate rows in the
streaming insert buffer. It is recommended that you use it. You'll still have to
provide an authenticated instance of google.cloud.bigquery.client.Client.

See
[this change](https://chrome-internal-review.googlesource.com/c/407748/)
for a simple example. (TODO: replace with a non-internal example that uses
BigQueryHelper.) The [API
docs](https://googlecloudplatform.github.io/google-cloud-python/stable/bigquery-usage.html)
can also be helpful.

# (Optional Step) Writing a Dataflow workflow

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

The builder name should be `dataflow-workflow-[job name]` where job name is
the name of the remotely executed job. This naming scheme sets up automated
alerting for builder failures.

# Step 3: Analyze/Track/Graph Events

TODO
