# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Post-processing steps applied to uploaded package instances."""

import logging


class ProcessingError(Exception):
  """Fatal error during processing.

  Exception message will be stored as ProcessingResult.error.
  """


class Processor(object):
  """Object that runs some post processing step on a package instance data."""

  # Must be set in subclasses, identifies the processor kind.
  name = None

  def should_process(self, instance):
    """Returns True if this processor should process given PackageInstance."""
    raise NotImplementedError()

  def run(self, instance, data):
    """Runs the processing step on the package instance.

    It must be idempotent. The processor may be called multiple times for same
    package (when retrying task queue tasks and so on).

    Args:
      instance: PackageInstance entity to process.
      data: PackageReader that can be used to read package data.

    Returns:
      JSON serializable data (e.g. dict, lists, etc) to store in
      ProcessingResult.result field.

    Exceptions that can be raised to fail the step:
      ProcessingError - generic fatal error raised by the processor itself.
      ReaderError - fatal error when reading package file.

    Any other exception (deadlines of various sorts, InternalErrors, Cloud
    Storage flakes, etc, etc.) are considered transient errors and trigger
    retry of the processing task.
    """
    raise NotImplementedError()


class DummyProcessor(Processor):  # pragma: no cover
  """Does nothing, just and example. To be removed later."""

  name = 'dummy:v1'

  def should_process(self, instance):
    return instance.package_name.startswith('playground/')

  def run(self, instance, data):
    logging.info('Package files: %s', data.get_packaged_files())
    return {
      'instance_id': instance.instance_id,
      'package_name': instance.package_name,
    }
