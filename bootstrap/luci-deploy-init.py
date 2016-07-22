#!/usr/bin/env python
# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a script run by the LUCI deployment tool to initialize this
repository's source.

Specifically, this runs the "go/deps.py" bootstrap in order to checkout the
Go dependencies and emits a result to the deployment tool describing the
output of the bootstrap as per the `SourceLayout.Init.PythonScript` protocol
described here:

https://github.com/luci/luci-go/blob/master/deploytool/api/deploy/checkout.proto
"""

import argparse
import imp
import json
import os
import subprocess
import sys


INFRA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
INFRA_GO_PATH = os.path.join(INFRA_PATH, 'go')
INFRA_GO_VENDOR_SRC_PATH = os.path.join(INFRA_GO_PATH, '.vendor', 'src')

# Do not want to mess with sys.path, load the module directly.
go_deps = imp.load_source(
    'deps', os.path.join(INFRA_GO_PATH, 'deps.py'))


# Used to constructed repeated `go_path` entries in the SourceInitResult proto
# message.
_GOPATH_PROTOBUF_ENTRY_TEMPLATE = """\
go_path <
  path: "%(path)s"
  go_package: "%(package)s"
>
"""


def _go_pkg_deploy_path(base, pkg):
  return os.path.join(base, pkg.replace('/', os.sep)).replace(os.sep, '/')


def main(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument('source_root',
      help='The path to the source root to initialize.')
  parser.add_argument('result_path',
      help='The path to write the result file.')
  opts = parser.parse_args(argv)

  # Update our deps.
  rv = go_deps.install(INFRA_GO_PATH)
  if rv != 0:
    print 'Failed to install dependencies.'
    return rv

  # Get our source root-relative path.
  go_src_relpath = os.path.relpath(INFRA_GO_VENDOR_SRC_PATH, opts.source_root)

  # Run our "Go" bootstrap.
  deps_path = os.path.join(INFRA_GO_PATH, 'deps.lock')
  deps = go_deps.parse_glide_lock(go_deps.read_file(deps_path))

  with open(opts.result_path, 'w') as fd:
    for entry in deps.get('imports', ()):
      pkg = entry['name']
      fd.write(_GOPATH_PROTOBUF_ENTRY_TEMPLATE % {
          'path': _go_pkg_deploy_path(go_src_relpath, pkg),
          'package': pkg,
      })
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
