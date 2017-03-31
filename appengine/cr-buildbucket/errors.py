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


class TagIndexIncomplete(Error):
  """Raised when a tag index is permanently incomplete and cannot be used."""


class InvalidIndexEntryOrder(Error):
  """Raised when tag index entry order is incorrect."""


def validate_bucket_name(bucket, project_id=None):
  """Raises InvalidInputError if bucket name is invalid."""
  if not bucket:
    raise InvalidInputError('Bucket not specified')
  if (project_id and bucket.startswith('luci.')
      and not bucket.startswith('luci.%s.' % project_id)):
    raise InvalidInputError(
        'Bucket must start with "luci.%s." because it starts with "luci." '
        'and is defined in the %s project' % (project_id, project_id))

  if not isinstance(bucket, basestring):
    raise InvalidInputError(
      'Bucket must be a string. It is %s.' % type(bucket).__name__)
  if not BUCKET_NAME_REGEX.match(bucket):
    raise InvalidInputError(
      'Bucket name "%s" does not match regular expression %s' %
      (bucket, BUCKET_NAME_REGEX.pattern))
