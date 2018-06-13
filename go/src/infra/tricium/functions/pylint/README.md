# Pylint

Tricium analyzer checking for checking Python code.

Consumes Tricium FILES and producs Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ go build
$ ./ --input=test --output=output
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ go build
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/pylint -ref live -version VERSION
```
