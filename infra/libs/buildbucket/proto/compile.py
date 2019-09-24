#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Copies .proto files from buildbucket Go.

This ugly script copies files from
../../../go/src/go.chromium.org/luci/buildbucket/proto/
to this dir and modifies them to make them usable from Python.

The reason they are not usable as is is cproto requires protos in Go to use
go-style absolute import paths, e.g.
  import "github.com/user/repo/path/to/file.proto"
which results in Python import
  import github.com.user.repo.path.to.file
"""

import os
import re
import subprocess
import shutil
import tempfile

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

INFRA_ROOT = os.path.normpath(os.path.join(THIS_DIR, '..', '..', '..', '..'))
LUCI_GO_DIR = os.path.join(INFRA_ROOT, 'go', 'src', 'go.chromium.org', 'luci')
COMPONENTS_TOOLS_DIR = os.path.join(
    INFRA_ROOT, 'luci', 'appengine', 'components', 'tools'
)
RPC_PROTO_DIR = os.path.join(LUCI_GO_DIR, 'grpc', 'proto')
COMMON_PROTO_DIR = os.path.join(LUCI_GO_DIR, 'common', 'proto')
BUILDBUCKET_PROTO_DIR = os.path.join(LUCI_GO_DIR, 'buildbucket', 'proto')
SWARMING_PROTO = os.path.join(
    LUCI_GO_DIR, 'swarming', 'proto', 'api', 'swarming.proto'
)


def modify_proto(src, dest):
  with open(src) as f:
    contents = f.read()

  # Rewrite imports.
  contents = re.sub(
      r'import "go\.chromium\.org/.+/([^"/]+)";',
      r'import "\1";',
      contents,
  )

  with open(dest, 'w') as f:
    f.write(contents)


def find_files(path, suffix=''):
  return [os.path.join(path, f) for f in os.listdir(path) if f.endswith(suffix)]


def main():
  tmpd = tempfile.mkdtemp(suffix='buildbucket-proto')

  proto_files = find_files(BUILDBUCKET_PROTO_DIR, suffix='.proto')
  proto_files += [SWARMING_PROTO]
  proto_files += find_files(COMMON_PROTO_DIR, suffix='.proto')
  # Copy modified .proto files into temp dir.
  for f in proto_files:
    modify_proto(f, os.path.join(tmpd, os.path.basename(f)))

  # Compile them.
  args = [
      'protoc',
      '-I',
      RPC_PROTO_DIR,
      '-I',
      tmpd,
      '--python_out=.',
      '--prpc-python_out=.',
  ]
  args += [os.path.join(tmpd, f) for f in os.listdir(tmpd)]

  # Include protoc-gen-prpc-python in $PATH.
  env = os.environ.copy()
  env['PATH'] = '%s%s%s' % (COMPONENTS_TOOLS_DIR, os.path.pathsep, env['PATH'])

  subprocess.check_call(args, cwd=tmpd, env=env)
  pb2_files = find_files(tmpd, suffix='_pb2.py')

  # Remove all _pb2.py and .pyc from the dest dir
  for fname in os.listdir(THIS_DIR):
    if fname.endswith(('_pb2.py', '.pyc')):
      os.remove(os.path.join(THIS_DIR, fname))

  # Copy _pb2.py files to dest dir.
  for f in pb2_files:
    shutil.copyfile(f, os.path.join(THIS_DIR, os.path.basename(f)))


if __name__ == '__main__':
  main()
