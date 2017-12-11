# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Manages the raw sources needed to build wheels.

A source has a remote (public) address. That file is then downloaded and cached
locally as a CIPD package in the "infra/third_party/source" CIPD tree.

Systems that want to operate on a source reference it by a source constant, or
by a constructor (e.g., Pip).
"""

import collections
import contextlib
import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

from . import cipd
from . import util


class Source(collections.namedtuple('Source', (
  'name', # The name of the source.
  'version', # The version of the source.
  'download_type', # Type of download function to use.
  'download_meta', # Arbitrary metadata to pass to download function.
  ))):

  # A registry of all created Source instances.
  _REGISTRY = {}

  def __new__(cls, *args, **kwargs):
    src = super(Source, cls).__new__(cls, *args, **kwargs)

    # Register source with "_REGISTRY" and enforce that any source with the same
    # (name, version) is defined exactly the same.
    #
    # NOTE: If this expectation is ever violated, we will need to update CIPD
    # source package naming to incorporate the difference.
    key = (src.name, src.version)
    current = cls._REGISTRY.get(key)
    if not current:
      cls._REGISTRY[key] = src
    elif current != src:
      raise ValueError('Incompatible source definitions (%r != %r)' % (
          current, src))

    return src

  @classmethod
  def all(cls):
    return cls._REGISTRY.values()

  @property
  def tag(self):
    return '%s-%s' % (self.name, self.version)


class Repository(object):

  # Map of "download_type" to download function. Mapping will be made
  # later as functions are defined.
  _DOWNLOAD_MAP = {}

  def __init__(self, system, workdir, upload=False, force_download=False):
    self._system = system
    self._root = workdir
    self._upload = upload
    self._force_download = force_download

    # Will be set to True if a source was encountered without a corresponding
    # CIPD package, but not uploaded to CIPD.
    self._missing_sources = False

    # Build our archive suffixes.
    self._archive_suffixes = collections.OrderedDict()
    for suffix in ('.tar.gz', '.tgz', '.tar.bz2'):
      self._archive_suffixes[suffix] = self._unpack_tar_generic
    for suffix in ('.zip',):
      self._archive_suffixes[suffix] = self._unpack_zip_generic

  @property
  def missing_sources(self):
    return self._missing_sources

  def ensure(self, src, dest_dir, unpack=True):
    util.LOGGER.debug('Ensuring source %r', src.tag)

    # Check if the CIPD package exists.
    package = cipd.Package(
        name=cipd.normalize_package_name(
          'infra/third_party/source/%s' % (src.name,)),
        tags=(
          'version:%s' % (src.version,),
        ),
        install_mode=cipd.INSTALL_SYMLINK,
        compress_level=cipd.COMPRESS_NONE,
    )
    package_path = os.path.join(self._root, '%s.pkg' % (src.tag,))
    package_dest = util.ensure_directory(self._root, src.tag)

    # If the package doesn't exist, or if we are forcing a download, create a
    # local package.
    cipd_exists = self._system.cipd.exists(package.name, package.tags[0])

    have_package = False
    if os.path.isfile(package_path):
      # Package file is on disk, reuse unless we're forcing a download.
      if not self._force_download:
        have_package = True

    if not have_package:
      # We need to acquire the package. If it doesn't exist remotely, or if
      # we're forcing a download, build it from source.
      if not cipd_exists or self._force_download:
        self._create_cipd_package(package, src, package_path)
      else:
        self._system.cipd.fetch_package(package.name, package.tags[0],
                                        package_path)
      have_package = True

    # We must have acquired the package at "package_path" by now.
    assert have_package

    # If we built a CIPD package, upload it. This will be fatal if we could not
    # perform the upload; if a user wants to not care about this, set "upload"
    # to False.
    if not cipd_exists:
      if self._upload:
        self._system.cipd.register_package(package_path, *package.tags)
        util.LOGGER.info('Uploaded CIPD source package')
      else:
        self._missing_sources = True
        util.LOGGER.warning('Missing CIPD package, but not uploaded.')

    # Install the CIPD package into our source directory. This is a no-op if it
    # is already installed.
    self._system.cipd.deploy_package(package_path, package_dest)

    # The package directory should contain exactly one file.
    package_files = [f for f in os.listdir(package_dest)
                     if not f.startswith('.')]
    if len(package_files) != 1:
      raise ValueError('Package contains %d (!= 1) files: %s' % (
          len(package_files), package_dest))
    package_file = package_files[0]
    package_file_path = os.path.join(package_dest, package_file)

    # Unpack or copy the source file into the destination path.
    if unpack:
      for suffix, unpack_func in self._archive_suffixes.iteritems():
        if package_file.endswith(suffix):
          return self._unpack_archive(package_file_path, dest_dir, unpack_func)

    # Single file.
    dest = os.path.join(dest_dir, os.path.basename(package_file))
    util.LOGGER.debug('Installing source from [%s] => [%s]', package_file, dest)
    shutil.copyfile(package_file_path, dest)
    return dest

  def _create_cipd_package(self, package, src, package_path):
    # Download to a temporary file.
    with self._system.temp_subdir(src.tag) as tdir:
      download_dir = util.ensure_directory(tdir, 'download')
      package_dir = util.ensure_directory(tdir, 'package')

      path = os.path.join(download_dir, 'file')
      util.LOGGER.debug('Downloading source to: [%s]', path)
      with open(path, 'wb') as fd:
        filename = self._DOWNLOAD_MAP[src.download_type](fd, src.download_meta)

      # Move the downloaded "file" into the package under its download name and
      # package it.
      os.rename(path, os.path.join(package_dir, filename))
      self._system.cipd.create_package(package, package_dir, package_path)

  def _unpack_archive(self, path, dest_dir, unpack_func):
    with self._system.temp_subdir(os.path.basename(path)) as tdir:
      unpack_func(path, tdir)

      contents = os.listdir(tdir)
      if len(contents) != 1:
        raise ValueError('Archive contained %d (!= 1) file(s)' % (
            len(contents),))

      archive_base = os.path.join(tdir, contents[0])
      dest = os.path.join(dest_dir, os.path.basename(archive_base))
      os.rename(archive_base, dest)
    return dest

  @staticmethod
  def _unpack_tar_generic(path, dest_dir):
    with tarfile.open(path, 'r') as tf:
      tf.extractall(dest_dir)

  @staticmethod
  def _unpack_zip_generic(path, dest_dir):
    with zipfile.ZipFile(path, 'r') as zf:
      zf.extractall(dest_dir)


def remote_file(name, version, url):
  return Source(
    name=name,
    version=version,
    download_type='url',
    download_meta=url,
  )


def remote_archive(name, version, url):
  return Source(
    name=name,
    version=version,
    download_type='url',
    download_meta=url,
  )


def _download_url(fd, meta):
  url = meta
  return util.download_to(url, fd)
Repository._DOWNLOAD_MAP['url'] = _download_url


def _download_pypi_archive(fd, meta):
  name, version = meta

  url = 'http://pypi.python.org/pypi/%s/%s/json' % (name, version)
  content = util.download_json(url)
  release = content.get('releases', {}).get(version)
  if not release:
    raise ValueError('No PyPi release for package %r at version %r' % (
        name, version))

  entry = None
  for entry in release:
    if entry.get('packagetype') == 'sdist':
      break
  else:
    raise ValueError('No PyPi source distribution for package %r at version '
                     '%r' % (name, version))

  hash_obj = None
  expected_hash = entry.get('md5')
  if expected_hash:
    hash_obj = hashlib.md5()

  url = entry['url']
  util.LOGGER.debug('Downloading package %r @ %r from PyPi: %s',
                    name, version, url)
  filename = util.download_to(url, fd, hash_obj=hash_obj)

  if hash_obj:
    download_hash = hash_obj.hexdigest().lower()
    if download_hash != expected_hash:
      raise ValueError("Download hash %r doesn't match expected hash %r." % (
          download_hash, expected_hash))

  return filename
Repository._DOWNLOAD_MAP['pypi_archive'] = _download_pypi_archive


def _download_local(fd, meta):
  basename = os.path.basename(meta)
  with tarfile.open(mode='w:bz2', fileobj=fd) as tf:
    tf.add(meta, arcname=basename)
  return '%s.tar.bz2' % (basename,)


def local_directory(name, version, path):
  return Source(
      name=name,
      version=version,
      download_type='local_directory',
      download_meta=path)
Repository._DOWNLOAD_MAP['local_directory'] = _download_local


def pypi_sdist(name, version):
  """Defines a Source whose remote data is a PyPi source distribution."""

  return Source(
    name=name,
    version=version,
    download_type='pypi_archive',
    download_meta=(name, version),
  )
