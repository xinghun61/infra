# ShellCheck

Tricium analyzer checking for checking shell code.

https://github.com/koalaman/shellcheck/wiki/SC1049

Consumes Tricium FILES and producs Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ make testrun
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ cipd create -pkg-def cipd.yaml
# outputs <VERSION>
$ cipd set-ref infra/tricium/function/shellcheck -ref live -version <VERSION>
```
