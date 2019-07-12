# Pylint

Tricium analyzer checking for checking Python code.

Consumes Tricium FILES and producs Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ go build -o pylint_parser
$ ./pylint_parser --input=test --output=out
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ go build -o pylint_parser
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/pylint -ref live -version VERSION
```
