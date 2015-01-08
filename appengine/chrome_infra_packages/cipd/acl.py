# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Access control list implementation."""

# Silence pylint warning until implementation is ready.
# pylint: disable=unused-argument

from components import auth

# TODO(vadimsh): Implement.


def can_fetch_instance(package_name, identity):  # pragma: no cover
  """True if |identity| is allowed to fetch an instance with given name."""
  return auth.is_admin(identity)


def can_register_instance(package_name, identity):  # pragma: no cover
  """True if |identity| is allowed to register an instance with given name."""
  return auth.is_admin(identity)
