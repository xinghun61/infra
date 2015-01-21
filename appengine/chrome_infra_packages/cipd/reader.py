# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Defines PackageReader class that knows how to read package file."""

import collections
import logging
import zipfile

# For cas.NotFoundError.
import cas


# Information about single file in the package.
PackagedFileInfo = collections.namedtuple('PackagedFileInfo', ['path', 'size'])


class ReaderError(Exception):
  """Base class for exception from this module."""


class BadPackageError(ReaderError):
  """Raised by package reader methods if package file is missing or broken."""


class NoSuchPackagedFileError(ReaderError):
  """Raised by 'open_packaged_file' if requested file is not in the package."""


class PackageReader(object):
  """Knows how to read contents of a package file."""

  def __init__(self, cas_service, hash_algo, hash_digest):
    self.cas_service = cas_service
    self.hash_algo = hash_algo
    self.hash_digest = hash_digest
    self._raw = None
    self._zip = None
    self._dir = None

  def __enter__(self):
    return self

  def __exit__(self, *_args):
    self.close()
    return False

  def get_packaged_files(self):
    """Returns a tuple with PackagedFileInfo objects in the package.

    Raises:
      BadPackageError if package is missing or not a valid zip.
    """
    self.ensure_open()
    return self._dir

  def open_packaged_file(self, path):
    """Returns a file-like object with contents of a given package item.

    Raises:
      BadPackageError if package is missing or not a valid zip.
      NoSuchPackagedFileError if |path| is not in the package.
    """
    self.ensure_open()
    try:
      return self._zip.open(path)
    except zipfile.BadZipfile as exc:
      raise BadPackageError(str(exc))
    except KeyError:
      raise NoSuchPackagedFileError('File %s is not in the package' % path)

  def close(self):
    """Releases any open resources."""
    self._dir = None
    try:
      try:
        if self._zip:  # pragma: no branch
          self._zip.close()
          self._zip = None
      finally:
        if self._raw:  # pragma: no branch
          self._raw.close()
          self._raw = None
    except Exception as exc:  # pragma: no cover
      logging.error(
          'Ignoring exception when closing package file.\nFile: %s/%s\n\n%s',
          self.hash_algo, self.hash_digest, exc)

  def ensure_open(self):
    """Lazily opens zip file and reads its directory.

    Raises:
      BadPackageError if package is missing or not a valid zip.
    """
    if self._zip:
      return
    # Open underlying raw file.
    try:
      assert not self._raw
      # ZipFile makes lot of seeks when reading zip directory, smaller chunk
      # size helps here,
      self._raw = self.cas_service.open(
          hash_algo=self.hash_algo,
          hash_digest=self.hash_digest,
          read_buffer_size=256*1024)
    except cas.NotFoundError:
      raise BadPackageError('No package file')
    # Parse its zip directory.
    try:
      self._zip = zipfile.ZipFile(self._raw, 'r', zipfile.ZIP_DEFLATED)
      self._dir = tuple([
        PackagedFileInfo(i.filename, i.file_size)
        for i in self._zip.infolist()
      ])
    except zipfile.BadZipfile as exc:
      self.close()
      raise BadPackageError(str(exc))
    except:  # pragma: no cover
      self.close()
      raise
