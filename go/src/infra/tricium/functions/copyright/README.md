# Copyright Analyzer

Tricium analyzer checking for the appropriate copyright header in files.

Default header regex is:

Copyright 20[0-9][0-9] The [A-Za-z]* Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be found
in the LICENSE file.

Issues detected:

* MissingCopyright: Missing copyright statement
* IncorrectCopyright: Incorrect copyright text
* OutOfDateCopyright: Out of date text (with a (c) in the old Chromium standard)

Consumes Tricium FILES and produces Tricium RESULTS comments.

## Development and Testing

Local testing:

```
$ go build
$ ./copyright --input=test --output=output
```

## Deployment

Deploy a new version of the analyzer using CIPD:

```
$ go build
$ cipd create -pkg-def=cipd.yaml
<outputs the VERSION>
$ cipd set-ref infra/tricium/function/copyright -ref live -version VERSION
```
