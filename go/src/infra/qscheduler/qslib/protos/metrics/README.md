# Updating the BigQuery Schema for Task Events

The `metrics.proto` contained in this directory defines a `TaskEvent` message
that is used to record structured data about task events. When this proto is
modified, the BigQuery tables where the data is stored need to be modified as
well.

To create or update a bigquery table, run the following command:

`bqschemaupdater -table $PROJECT_ID.qs_events.task_events -message-dir . -message metrics.TaskEvent`

where `$PROJECT_ID` is the appengine project ID, for instance
`qscheduler-swarming`.