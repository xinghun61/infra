# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides functions for handling tokens."""

from components import auth
import model


class BuildToken(auth.TokenKind):
  """Used for generating tokens to validate build messages."""
  expiration_sec = model.BUILD_TIMEOUT.total_seconds()
  secret_key = auth.SecretKey('build_id')


def _token_message(build_id, task_key):
  assert isinstance(build_id, (int, long)), build_id
  assert task_key is None or (isinstance(task_key, basestring) and task_key)
  # TODO(nodir): always require task_key.
  if task_key:
    return [str(build_id), task_key]
  return str(build_id)


def generate_build_token(build_id, task_key):
  """Returns a token associated with the build."""
  return BuildToken.generate(_token_message(build_id, task_key))


def validate_build_token(token, build_id, task_key):
  """Raises auth.InvalidTokenError if the token is invalid."""
  return BuildToken.validate(token, _token_message(build_id, task_key))
