# Gosec

Tricium analyzer checking for flagging security issues in Go code.

Consumes Tricium FILES and producs Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ make gosec_wrapper
$ ./gosec_wrapper --input=test --output=out
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ make cipd

$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/gosec -ref live -version VERSION
```
