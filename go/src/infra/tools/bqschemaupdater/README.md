bqschemaupdater is a tool for adding and updating BigQuery table schema.

It currently creates tables in the "chrome-infra-events" cloud project by
default. We can add support for different projects when needed in the future.

# Usage

```
bqschemaupdater <path to json schema file> [--help] [--dry-run]
```

# Standard Practices

Table IDs should be underscored delimited, e.g. `test_results`.

# Supported Uses

The operations supported by this tool include:

* Creating a new table
* Adding NULLABLE or REPEATED columns to an existing table
* Making REQUIRED fields NULLABLE in an existing table

## Schema Generation

The [bqexport](../../cmd/bqexport) tool is a Go generator utility
that can generate `bqschemaupdater`-compatible table definitions from BigQuery
Go structs. See [bqexport documentation](../../cmd/bqexport) for
more information.
