# Git File Isolator Analyzer

Consuming Tricium GIT_FILE_DETAILS data and producing a Tricium FILES data.

## Development and Testing

Local testing:

```
$ go build -o isolator
$ ./isolator --input=test --output=out
```

## Deployment

Deploy a new version of the isolator function using CIPD:

```
$ go build -o isolator
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/git-file-isolator -ref live -version VERSION
```
