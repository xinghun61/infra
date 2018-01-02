# Workflow Testing

To test that your pipeline will run remotely, you can use the command below.

You must first create Google Storage buckets to pass with the --staging_location
and --temp_location options. The name is not important, but for example you
could use `gs://my-dataflow-job/staging`.

```
python <path-to-dataflow-job> --job_name <pick-a-job-name> \
--project <project> --runner DataflowRunner \
--setup_file <infra-checkout-path>/packages/dataflow/setup.py \
--staging_location <staging bucket> \
--temp_location <temp bucket> --save_main_session
```

Job names should match the regular expression [a-z]\([-a-z0-9]{0,38}[a-z0-9]).
Navigate to the Dataflow console for your project in your browser and you should
see your job running. Wait until it succeeds.
