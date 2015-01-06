// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package cipd implements client side of Chrome Infra Package Deployer.

TODO: write more.

Binary package file format (in free form representation):
  <binary package> := <zipped data>
  <zipped data> := DeterministicZip(<all input files> + <manifest json>)
  <manifest json> := File{
    name: ".cipdpkg/manifest.json",
    data: JSON({
      "FormatVersion": "1",
      "PackageName": <name of the package>
    }),
  }
  DeterministicZip = zip archive with deterministic ordering of files and stripped timestamps

Main package data (<zipped data> above) is deterministic, meaning its content
depends only on inputs used to built it (byte to byte): contents and names of
all files added to the package (plus 'executable' file mode bit) and a package
name (and all other data in the manifest).

Binary package data MUST NOT depend on a timestamp, hostname of machine that
built it, revision of the source code it was built from, etc. All that
information will be distributed as a separate metadata packet associated with
the package when it gets uploaded to the server.

TODO: expand more when there's server-side package data model (labels
and stuff).
*/
package cipd

import "github.com/Sirupsen/logrus"

// Default package level logger.
var log = logrus.New()
