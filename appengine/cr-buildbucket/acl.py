# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(nodir): write tests for ACL

# pylint: disable=W0613

from components import auth


ACCESS_GROUP = 'buildbucket-access'


def is_access_group_member(identity):  # pragma: no cover
  return auth.is_group_member(ACCESS_GROUP, identity)


def can_add_build_to_bucket(bucket, identity):  # pragma: no cover
  return is_access_group_member(identity)


def can_peek_bucket(bucket, identity):  # pragma: no cover
  return is_access_group_member(identity)


def can_lease_build(build, identity):  # pragma: no cover
  return is_access_group_member(identity)


def can_cancel_build(build, identity):  # pragma: no cover
  return is_access_group_member(identity)


def can_view_build(build, identity):  # pragma: no cover
  return is_access_group_member(identity)
