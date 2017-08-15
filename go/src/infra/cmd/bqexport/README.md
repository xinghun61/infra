bqexport is a `go:generate` utility to export BigQuery schema protobufs compatible
with [bqschemaupdater](../../tools/bqschemaupdater). These protobufs can then be
loaded into BigQuery to instantiate your tables.

# Usage

Create a Go package for your scheme. This package must not be a `main` package,
or it can't be ingested by `bqexport`.

1. Declare a [Cloud BigQuery](https://godoc.org/cloud.google.com/go/bigquery)-
   compatible Go struct representing your schema.
1. Create a [tabledef](../../libs/bqschema/tabledef) struct
   describing your table.
1. Add a `go:generate` line in your Go package, redirecting its output to the
   `bqschemaupdater` JSON directory:
    ```go
    //go:generate go install infra/cmd/bqexport
    //go:generate bqexport -name MySchemaStruct -out /path/to/bqschemaupdater/myschema.json
    ```

By default, the table definition will be inferred by adding `Table` to the end
of you schema struct name (e.g., `MySchema` would have a corresponding
`MySchemaTable`).

## Optional Fields

Currently, BigQuery's `InferSchema` method marks all inferred fields as
required. A
[feature request](https://github.com/GoogleCloudPlatform/google-cloud-go/issues/726)
was made to add this natively to the `bigquery` package.

In the meantime, additional modifications are supported via the `bqexport` tag:

- **req** marks a field as required. By default, all fields are optional.
- **d=** marks the beginning of a description entry. The remainder of the
  `bqexport` tag, including commas, will be read as the description.

For example:

```go
type MySchema struct {
	RequiredField `bigquery:"required_field" bqexport:"req,d=This is a required field"`
	OptionalField `bigquery:"optional_field" bqexport:"d=This field is optional, which is cool."`
}
```
