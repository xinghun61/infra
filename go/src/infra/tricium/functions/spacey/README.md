# Spacey

Tricium analyzer checking for spacing issues.

Issues detected:

* TabSpaceMix: A Mix of tabs and spaces.
* TrailingSpace: Trailing spaces on a line.

Consumes Tricium FILES and producs Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ go build
$ ./spacey --input=test --output=output
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ go build
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/analyzer/spacey -ref live -version VERSION
```
