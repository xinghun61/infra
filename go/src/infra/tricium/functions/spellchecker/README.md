# Spellchecker

Tricium analyzer to check spelling.

Consumes Tricium FILES and produces Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ go build
$ ./spellchecker --input=test --output=out
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ make
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/spellchecker -ref live -version VERSION
```