# Eslint Parser

Tricium analyzer checking for checking Javascript code.

Consumes Tricium FILES and produces Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ make
$ ./eslint_parser --input=test --output=out
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ make
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/eslint -ref live -version VERSION
```
