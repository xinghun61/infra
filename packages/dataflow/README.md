# packages/dataflow

The purpose of this package is to simplify the development of Dataflow
workflows.

See the modules in [common](./common/README.md) for some generally useful
abstractions.

You'll notice that workflows are included in this package. Workflows are located
here to simplify job execution, as all non-[standard](https://beam.apache.org/documentation/)
and non-[beam](https://beam.apache.org/documentation/) modules must be packaged
together for job execution.

See
[Scheduling a Dataflow workflow](https://chromium.googlesource.com/infra/infra/+/master/doc/users/event_pipeline.md#scheduling-a-dataflow-workflow)
for more information on automating a workflow you'd like to run regularly.

It's possible that you may only care about running your pipeline locally. In
that case, you can simply import the common modules.

Note that Dataflow supports continuous pipelines. Chrome Operations hasn't
experimented with these yet, but they are worth exploring!

[TOC]

# References

[Beam Docs](https://beam.apache.org/documentation/)

# Unit Testing

From the root of the infra repository, run the command
```
./test.py test packages/dataflow
```

# Workflow Testing

There are a couple requirements to testing your Dataflow workflow.

First, you must activate the infra Python environment. Assuming you have that
set up already, run `source ENV/bin/activate` from the root of your infra
checkout. If you need to set up or update your environment, see
[bootstrap/README](../../bootstrap/README.md) for more info.

Next, you must have Google Storage buckets to pass with the --staging_location
and --temp_location options. The name is not important, but for example you
could use `gs://my-dataflow-job/staging`. [Create these](https://cloud.google.com/storage/docs/creating-buckets)
if you don't have them already.

Next, you must have permission within the project to schedule a Dataflow job,
and be authenticated to do so.

To check your
authentication status, ensure that you have the Cloud SDK
[installed](https://cloud.google.com/sdk/docs/quickstarts), then run:

```
gcloud info
```

If you don't see the correct project id, reach out to an
[editor](https://pantheon.corp.google.com/iam-admin/iam) of that project to
request access.

Finally, run the command below to test your workflow as a remote job. Note: Job
names should match the regular expression [a-z]\([-a-z0-9]{0,38}[a-z0-9]).

```
python <path-to-dataflow-job> --job_name <pick-a-job-name> \
--project <project> --runner DataflowRunner \
--setup_file <infra-checkout-path>/packages/dataflow/setup.py \
--staging_location <staging bucket> \
--temp_location <temp bucket> --save_main_session
```
Navigate to the [Dataflow console](https://console.cloud.google.com/project) in
your browser and you should see your job running. Wait until it succeeds.

Running the test will leave behind a directory,
`packages/dataflow/dataflow.egg-info`, that you must manually clean up.

To run the workflow locally, first set credentials using
```
export GOOGLE_APPLICATION_CREDENTIALS=<path_to_credentials>
```

Then
```
python cq_attempts.py --output <dummy_path> --project <name_of_test_project>
```

# Updating the package

Changes to this directory are automatically mirrored in a synthesized
[repo](https://chromium.googlesource.com/infra/infra/packages/dataflow/). To
deploy changes to this repository:
* Land the changes.
* Submit a separate CL that updates the version in `setup.py`.
* Build and upload a new wheel.
* Submit a single CL that updates the remote execution recipe and deps.pyl.

Jobs scheduled with the
[remote_execute_dataflow_workflow](../../recipes/recipes/remote_execute_dataflow_workflow.py)
recipe use the version of the job at HEAD but the version of the package pinned
in [bootstrap/deps.pyl](../../bootstrap/deps.pyl). So, if you make a breaking
change to the package, submit the update first (which will automatically be
picked up by the [package
mirror](https://chromium.googlesource.com/infra/infra/packages/dataflow/)),
then submit the change to the job along with the ref update in deps.pyl together
in one commit. Be sure to follow the instructions in [bootstrap/README.md](../../bootstrap/README.md)
to build and upload the new wheel before submitting the change to deps.pyl.

# Limits

Please see the [Dataflow docs](https://cloud.google.com/dataflow/quotas) for the
most up to date information on quotas and limits.

At the time of writing, there are limits on Dataflow requests per minute, number
of GCE instances (--numWorkers), number of concurrent jobs, monitoring requests,
job creation request size, and number of side input shards.

Some of these limits are per user, others are per project, others are per
organization. In general, users and project owners are responsible for ensuring
they do not hit user and project limits. Currently these limits are, in general,
not restrictive for us, and we are not concerned about hitting them.

## Interaction with other cloud services

If you run a job on GCE, GCE limits apply. If you use BigQuery as a source or
sink, BigQuery limits apply. Project owners should monitor usage and be mindful
of these limits.

### BigQuery

The relevant limits are query and insert limits.
[Query](https://cloud.google.com/bigquery/quotas#queries) and
[insert](https://cloud.google.com/bigquery/quotas#streaminginserts) limits can
be found in the Dataflow documentation. As query and insert rates are highly
project-specific, project owners should be responsible for monitoring this
limit.
