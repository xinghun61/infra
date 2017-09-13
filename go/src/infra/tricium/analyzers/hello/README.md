# Hello Analyzer

Consuming Tricium GIT_FILE_DETAILS and producing a Tricium RESULTS comment.

Deploy a new version of the analyzer using CIPD:

```
$ cipd create -pkg-def=cipd.yaml
```

TODO(emso): Makes this analyzer depend on FILES and produce a comment per file.
