# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implements the main creation logic.

This defines the encapsulating logic for fetching, building, packaging, testing
and uploading a ResolvedSpec.
"""

from . import spec_pb2

from . import source

from .workdir import Workdir


def build_resolved_spec(api, spec, version, spec_lookup, cache):
  """Builds a resolved spec at a specific version, then uploads it.

  Args:
    * api - The ThirdPartyPackagesNGApi's `self.m` module collection.
    * spec (ResolvedSpec) - The resolved spec to build.
    * version (str) - The symver (or 'latest') version of the package to build.
    * spec_lookup ((package_name, platform) -> ResolvedSpec) - A function to
      lookup (possibly cached) ResolvedSpec's for things like dependencies and
      tools.
    * cache (dict) - A map of (package_name, version, platform) -> CIPDSpec.
      The `build_resolved_spec` function fully manages the content of this
      dictionary.

  Returns the CIPDSpec of the built package; If the package already existed on
  the remote server, it will return the CIPDSpec immediately (without attempting
  to build anything).
  """
  keys = [(spec.name, version, spec.platform)]
  if keys[0] in cache:
    return cache[keys[0]]

  def set_cache(spec):
    for k in keys:
      cache[k] = spec
    return spec

  with api.step.nest('building %s' % (spec.name.encode('utf-8'),)):
    env = {
      '_3PP_PLATFORM': spec.platform,
      '_3PP_PACKAGE_NAME': spec.name,
    }
    if spec.create_pb.source.patch_version:
      env['_3PP_PATCH_VERSION'] = spec.create_pb.source.patch_version

    with api.context(env=env):
      # Resolve 'latest' versions. Done inside the env because 'script' based
      # sources need the $_3PP* envvars.
      is_latest = version == 'latest'
      if is_latest:
        version = source.resolve_latest(api, spec)
        keys.append((spec.name, version, spec.platform))
        if keys[-1] in cache:
          return set_cache(cache[keys[-1]])

      cipd_spec = spec.cipd_spec(version)
      # See if the specific version is uploaded
      if not cipd_spec.check():
        # Otherwise, build it
        _build_impl(api, spec, version, spec_lookup, cache)

      return set_cache(cipd_spec)


def _build_impl(api, spec, version, spec_lookup, cache):
  workdir = Workdir(api, spec, version)
  with api.context(env={'_3PP_VERSION': version}):
    api.file.ensure_directory('mkdir -p [workdir]', workdir.base)

    with api.step.nest('fetch sources'):
      source.fetch_source(
        api, workdir, spec, version, spec_lookup,
        lambda spec, version: build_resolved_spec(
          api, spec, version, spec_lookup, cache))

    # TODO(iannucci): build

    # TODO(iannucci): package

    # TODO(iannucci): verify

    # TODO(iannucci): upload
