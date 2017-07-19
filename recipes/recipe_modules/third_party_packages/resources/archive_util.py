# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Simplifies the extraction of archive files, and works under Windows."""

import argparse
import collections
import os
import sys
import tarfile
import zipfile


_UNPACK = collections.OrderedDict()


# ZipFile, by default, does not apply file attributes to the files that it
# extracts. This means that executable files don't get their executable bits
# set, resulting in an erroneous extraction.
#
# See:
# https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries
class AttrPreservingZipFile(zipfile.ZipFile):

  def extract(self, member, path=None, pwd=None):
    if not isinstance(member, zipfile.ZipInfo):
        member = self.getinfo(member)

    if path is None:
        path = os.getcwd()

    ret_val = self._extract_member(member, path, pwd)
    attr = member.external_attr >> 16
    os.chmod(ret_val, attr)
    return ret_val


def _unpack_zip(archive, dest):
  with AttrPreservingZipFile(archive, 'r') as fd:
    fd.extractall(dest)

_UNPACK['.zip'] = _unpack_zip


def _unpack_tar(archive, dest):
  with tarfile.open(archive, 'r') as tf:
    tf.extractall(dest)

_UNPACK['.tar.gz'] = _unpack_tar


def main(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument('archive',
      help='Path to the archive to unpack.')
  parser.add_argument('dest',
      help='Path to the destination directory to extract into.')
  args = parser.parse_args(argv)

  if not os.path.exists(args.dest):
    os.makedirs(args.dest)

  for ext, fn in _UNPACK.iteritems():
    if args.archive.lower().endswith(ext):
      fn(args.archive, args.dest)
      return 0

  raise ValueError(
      'No unpack strategy for %r.' % (os.path.basename(args.archive),))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
