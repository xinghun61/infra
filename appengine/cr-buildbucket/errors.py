# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


BUCKET_NAME_REGEX = re.compile(r'^[0-9a-z_\.\-/]{1,100}$')


class Error(Exception):
  pass


class BuildNotFoundError(Error):
  pass


class BuildIsCompletedError(Error):
  """Build is complete and cannot be changed."""


class InvalidInputError(Error):
  """Raised when service method argument value is invalid."""


class LeaseExpiredError(Error):
  """Raised when provided lease_key does not match the current one."""


def validate_bucket_name(bucket):
  """Raises InvalidInputError if bucket name is invalid."""
  if not bucket:
    raise InvalidInputError('Bucket not specified')
  if not isinstance(bucket, basestring):
    raise InvalidInputError(
        'Bucket must be a string. It is %s.' % type(bucket).__name__)
  if not BUCKET_NAME_REGEX.match(bucket):
    raise InvalidInputError(
        'Bucket name "%s" does not match regular expression %s' %
        (bucket, BUCKET_NAME_REGEX.pattern))
