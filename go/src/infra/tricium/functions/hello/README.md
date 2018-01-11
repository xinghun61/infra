# Hello Analyzer

Consuming Tricium FILES data and producing a Tricium RESULTS data with comments,
one per file in the FILES data.

## Development and Testing

Local testing:

```
$ go build
$ ./hello --input=test --output=output
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ go build
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/analyzer/hello -ref live -version VERSION
```
