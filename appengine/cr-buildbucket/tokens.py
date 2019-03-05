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


def generate_build_token(build_id):
  """Returns a token associated with the build."""
  return BuildToken.generate(str(build_id))


def validate_build_token(token, build_id):
  """Raises auth.InvalidTokenError if the token is invalid."""
  return BuildToken.validate(token, str(build_id))
