bqexport is a `go:generate` utility to generate Go structs based on BigQuery
schema protobufs compatible with [bqschemaupdater](../../tools/bqschemaupdater).
These structs can then be used in combination with
[eventupload](../../libs/eventupload) to send events to BigQuery.

# Usage

1. Create a [TableDef protobuf](../../libs/bqschema/tabledef/table_def.proto).
1. Once your protobuf has been reviewed and committed, run the bqexport command:
   `bqexport --help`. Don't have bqexport in your path? Try this inside the [infra
    Go env](../../../../env.py).
1. Add a `go:generate` line in `generate.go` in your Go package alongside your
generated file:

```go
//go:generate go install infra/cmd/bqexport
//go:generate bqexport -name MyStruct -path /path/to/tabledef.pb.txt
```
