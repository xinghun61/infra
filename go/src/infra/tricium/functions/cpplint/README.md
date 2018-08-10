# Cpplint Parser

Tricium analyzer checking for checking C++ code.

Consumes Tricium FILES and produces Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ make
$ ./cpplint_parser --input=test --output=out
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ make
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/cpplint -ref live -version VERSION
```
