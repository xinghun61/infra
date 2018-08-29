# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

import hashlib

from recipe_engine.recipe_api import Property
from recipe_engine.config import ConfigList, ConfigGroup, Single, List


DEPS = [
  'recipe_engine/properties',
  'recipe_engine/runtime',
]


PROPERTIES = {
  'package_locations': Property(
      help=('URL of repo containing package definitions.'
            'Cross-compiling requires docker on $PATH.'),
      kind=ConfigList(
        lambda: ConfigGroup(
          repo=Single(str),
          ref=Single(str, required=False),
          subdir=Single(str),
        ),
      )
  ),
  'to_build': Property(
    help=(
      'The names of the packages to build and upload. Leave empty to build '
      'and upload all known packages. Version should be like "1.2.3", or '
      '"latest" to resolve the latest known version from source.'),
    kind=ConfigList(
      lambda: ConfigGroup(
        name=Single(str),
        version=Single(str),
      )),
    default=(),
  ),
  'platform': Property(
      kind=str, default=None,
      help=(
        'Target platform. Must be a valid CIPD ${platform}. Cross-compiling '
        'requires docker on $PATH.')),
}


def RunSteps(api, package_locations, to_build, platform):
  # TODO(iannucci): implement
  _ = api
  _ = package_locations
  _ = to_build
  _ = platform


def GenTests(api):
  yield (
      api.test('basic') +
      api.properties(package_locations=[]) +
      api.runtime(is_luci=True, is_experimental=False))
