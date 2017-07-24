# Testing

To test that your pipeline will run remotely:

```
python <path-to-dataflow-job> --job_name <pick-a-job-name> \
--project chrome-infra-events --runner DataflowRunner --setup_file \
<infra-checkout-path>/packages/dataflow/setup.py \
--staging_location gs://dataflow-chrome-infra-events/staging --temp_location \
gs://dataflow-chrome-infra-events/temp --save_main_session
```

Job names should match the regular expression [a-z]\([-a-z0-9]{0,38}[a-z0-9]).
Navigate to the Dataflow console in your browser (project: chrome-infra-events)
and you should see your job running. Wait until it succeeds.
