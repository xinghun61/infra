# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Miscellaneous utility functions."""


import contextlib
import json
import shutil
import sys
import tempfile


def read_json_as_utf8(filename=None, text=None):
  """Read and deserialize a json file or string.

  This function is different from json.load and json.loads in that it
  returns utf8-encoded string for keys and values instead of unicode.

  Args:
    filename (str): path of a file to parse
    text (str): json string to parse

  ``filename`` and ``text`` are mutually exclusive. ValueError is raised if
  both are provided.
  """

  if filename is not None and text is not None:
    raise ValueError('Only one of "filename" and "text" can be provided at '
                     'the same time')

  if filename is None and text is None:
    raise ValueError('One of "filename" and "text" must be provided')

  def to_utf8(obj):
    if isinstance(obj, dict):
      return {to_utf8(key): to_utf8(value) for key, value in obj.iteritems()}
    if isinstance(obj, list):
      return [to_utf8(item) for item in obj]
    if isinstance(obj, unicode):
      return obj.encode('utf-8')
    return obj

  if filename:
    with open(filename, 'rb') as f:
      obj = json.load(f)
  else:
    obj = json.loads(text)

  return to_utf8(obj)


# We're trying to be compatible with Python3 tempfile.TemporaryDirectory
# context manager here. And they used 'dir' as a keyword argument.
# pylint: disable=redefined-builtin
@contextlib.contextmanager
def temporary_directory(suffix="", prefix="tmp", dir=None,
                        keep_directory=False):
  """Create and return a temporary directory.  This has the same
  behavior as mkdtemp but can be used as a context manager.  For
  example:

    with temporary_directory() as tmpdir:
      ...

  Upon exiting the context, the directory and everything contained
  in it are removed.

  Args:
    suffix, prefix, dir: same arguments as for tempfile.mkdtemp.
    keep_directory (bool): if True, do not delete the temporary directory
      when exiting. Useful for debugging.

  Returns:
    tempdir (str): full path to the temporary directory.
  """
  tempdir = None  # Handle mkdtemp raising an exception
  try:
    tempdir = tempfile.mkdtemp(suffix, prefix, dir)
    yield tempdir

  finally:
    if tempdir and not keep_directory:  # pragma: no branch
      try:
        # TODO(pgervais,496347) Make this work reliably on Windows.
        shutil.rmtree(tempdir, ignore_errors=True)
      except OSError as ex:  # pragma: no cover
        print >> sys.stderr, (
          "ERROR: {!r} while cleaning up {!r}".format(ex, tempdir))
