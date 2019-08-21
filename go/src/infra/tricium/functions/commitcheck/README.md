# Commitmsg Analyzer

Consuming Tricium FILES data and producing a Tricium RESULTS data with comments,
one per file in the FILES data.


It will check for the presence of both TEST= and BUG= entries, adding Gerrit
comments if absent. It will further verify the BUG= value itself.


## Development and Testing

Local testing:

```
$ go build
$ ./commitcheck --input=test --output=out
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ go build
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/commitcheck -ref live -version VERSION
```
