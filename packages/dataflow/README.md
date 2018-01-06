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

Finally, run the command below to test your workflow. Note: Job names should
match the regular expression [a-z]\([-a-z0-9]{0,38}[a-z0-9]).

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

# Updating the package

Jobs scheduled with the
[remote_execute_dataflow_workflow](../../recipes/recipes/remove_execute_dataflow_workflow.py)
recipe use the version of the job at HEAD but the version of the package pinned
in [bootstrap/deps.pyl](../../bootstrap/deps.pyl). So, if you make a breaking
change to the package, submit the update first (which will automatically be
picked up by the [package
mirror](https://chromium.googlesource.com/infra/infra/packages/dataflow/)),
then submit the change to the job along with the ref update in deps.pyl together
in one commit. Be sure to follow the instructions in [bootstrap/README.md](../../bootstrap/README.md)
to build and upload the new wheel before submitting the change to deps.pyl.
