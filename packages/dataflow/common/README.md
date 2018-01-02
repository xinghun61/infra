The `common` module provides reusable classes for writing Dataflow workflows.

## chops_beam

For easily constructing readable pipelines with standard defaults.

```
q = ('SELECT blah FROM `example_project.example_dataset.example_table`')
p = chops_beam.EventsPipeline()
_ = (p
     | chops_beam.BQRead(q)
     | ... # do some transforms
     | chops_beam.BQWrite('example_project', 'destination_table'))
p.run()
```

## objects

Convenient classes for BigQuery tables. Can be used for reading from or writing
to BigQuery.

```
for row in input_rows:
  event = objects.CQEvent.from_bigquery_row(row)
```

## combine_fns

Generally useful [Combine
Functions](https://beam.apache.org/documentation/programming-guide/#transforms-combine).
