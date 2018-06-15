# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions for build tags, colon-delimeted key-value pairs.

Many short functions are annotated with "pragma: no cover" because they are
covered by other modules.
"""

import errors
import re

DELIMITER = ':'

BUILDER_KEY = 'builder'
BUILD_ADDRESS_KEY = 'build_address'
BUILDSET_KEY = 'buildset'
SWARMING_TAG_KEY = 'swarming_tag'
SWARMING_DIMENSION_KEY = 'swarming_dimension'
RESERVED_KEYS = {
    BUILD_ADDRESS_KEY,
    SWARMING_TAG_KEY,
    SWARMING_DIMENSION_KEY,
}

BUILDSET_MAX_LENGTH = 1024

# Gitiles commit buildset pattern. Example:
# ('commit/gitiles/chromium.googlesource.com/infra/luci/luci-go/+/'
#  'b7a757f457487cd5cfe2dae83f65c5bc10e288b7')
RE_BUILDSET_GITILES_COMMIT = re.compile(
    r'^commit/gitiles/([^/]+)/(.+?)/\+/([a-f0-9]{40})$'
)
# Gerrit CL buildset pattern. Example:
# patch/gerrit/chromium-review.googlesource.com/677784/5
RE_BUILDSET_GERRIT_CL = re.compile(r'^patch/gerrit/([^/]+)/(\d+)/(\d+)$')


def builder_tag(builder):  # pragma: no cover
  return unparse(BUILDER_KEY, builder)


def build_address_tag(bucket, builder, number):  # pragma: no cover
  """Returns a build_address tag."""
  return unparse(BUILD_ADDRESS_KEY, build_address(bucket, builder, number))


def parse_build_address(address):
  """Parses a build address into its components. Opposite of build_address()."""
  parts = address.split('/', 2)
  if len(parts) != 3:
    raise ValueError('number of slashes must be exactly 2')
  try:
    number = int(parts[2])
  except ValueError:
    raise ValueError('invalid build number "%s"' % parts[2])
  return parts[0], parts[1], number


def parse(tag):  # pragma: no cover
  """Returns tuple (key, value) from the tag."""
  if DELIMITER not in tag:
    raise ValueError('tag must have ":"')
  return tag.split(DELIMITER, 1)


def unparse(key, value):  # pragma: no cover
  # """Returns a tag string from a key-value pair."""
  return '%s%s%s' % (key, DELIMITER, value)


def build_address(bucket, builder, number):  # pragma: no cover
  """Returns value for build_address tag."""
  return '%s/%s/%d' % (bucket, builder, number)


def gerrit_change_buildset(host, change, patchset):  # pragma: no cover
  return 'patch/gerrit/%s/%d/%d' % (host, change, patchset)


def git_commit_buildset(commit_hash):  # pragma: no cover
  return 'commit/git/' + commit_hash


def validate_tags(tags, mode, builder=None):
  """Validates build tags.

  mode must be a string, one of:
    'new': tags are for a new build.
    'append': tags are to be appended to an existing build.
    'search': tags to search by.

  builder is the value of "builder_name" parameter. If specified, tags
  "builder:<v>" must have v equal to the builder. Relevant only in 'new' mode.
  """
  assert mode in ('new', 'append', 'search'), mode
  if tags is None:
    return
  if not isinstance(tags, list):
    raise errors.InvalidInputError('tags must be a list')
  seen_builder_tag = None
  seen_gitiles_commit = False
  for t in tags:  # pragma: no branch
    if not isinstance(t, basestring):
      raise errors.InvalidInputError(
          'Invalid tag "%s": must be a string' % (t,)
      )
    if ':' not in t:
      raise errors.InvalidInputError(
          'Invalid tag "%s": does not contain ":"' % t
      )
    if t[0] == ':':
      raise errors.InvalidInputError('Invalid tag "%s": starts with ":"' % t)
    k, v = t.split(':', 1)
    if k == BUILDSET_KEY:
      try:
        validate_buildset(v)
      except errors.InvalidInputError as ex:
        raise errors.InvalidInputError('Invalid tag "%s": %s' % (t, ex))
      if RE_BUILDSET_GITILES_COMMIT.match(v):  # pragma: no branch
        if seen_gitiles_commit:
          raise errors.InvalidInputError(
              'More than one commits/gitiles buildset'
          )
        seen_gitiles_commit = True
    if k == BUILDER_KEY:
      if mode == 'append':
        raise errors.InvalidInputError(
            'Tag "builder" cannot be added to an existing build'
        )
      if mode == 'new':  # pragma: no branch
        if builder is not None and v != builder:
          raise errors.InvalidInputError(
              'Tag "%s" conflicts with builder_name parameter "%s"' %
              (t, builder)
          )
        if seen_builder_tag is None:
          seen_builder_tag = t
        elif t != seen_builder_tag:  # pragma: no branch
          raise errors.InvalidInputError(
              'Tag "%s" conflicts with tag "%s"' % (t, seen_builder_tag)
          )
    if mode != 'search' and k in RESERVED_KEYS:
      raise errors.InvalidInputError('Tag "%s" is reserved' % k)


def validate_buildset(bs):
  """Raises errors.InvalidInputError if the buildset is invalid."""
  if len(BUILDSET_KEY) + len(DELIMITER) + len(bs) > BUILDSET_MAX_LENGTH:
    raise errors.InvalidInputError('too long')

  # Verify that a buildset with a known prefix is well formed.
  if bs.startswith('commit/gitiles/'):
    m = RE_BUILDSET_GITILES_COMMIT.match(bs)
    if not m:
      raise errors.InvalidInputError(
          'does not match regex "%s"' % (RE_BUILDSET_GITILES_COMMIT.pattern)
      )
    project = m.group(2)
    if project.startswith('a/'):
      raise errors.InvalidInputError('gitiles project must not start with "a/"')
    if project.endswith('.git'):
      raise errors.InvalidInputError('gitiles project must not end with ".git"')

  elif bs.startswith('patch/gerrit/'):
    if not RE_BUILDSET_GERRIT_CL.match(bs):
      raise errors.InvalidInputError(
          'does not match regex "%s"' % RE_BUILDSET_GERRIT_CL.pattern
      )
