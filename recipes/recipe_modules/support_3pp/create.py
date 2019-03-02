# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implements the main creation logic.

This defines the encapsulating logic for fetching, building, packaging, testing
and uploading a ResolvedSpec.
"""

from . import source
from . import build
from . import verify

from .workdir import Workdir

from PB.recipe_modules.infra.support_3pp.spec import Spec


def build_resolved_spec(api, spec_lookup, cache, force_build, spec, version):
  """Builds a resolved spec at a specific version, then uploads it.

  Args:
    * api - The ThirdPartyPackagesNGApi's `self.m` module collection.
    * spec_lookup ((package_name, platform) -> ResolvedSpec) - A function to
      lookup (possibly cached) ResolvedSpec's for things like dependencies and
      tools.
    * cache (dict) - A map of (package_name, version, platform) -> CIPDSpec.
      The `build_resolved_spec` function fully manages the content of this
      dictionary.
    * force_build (bool) - If True, don't consult CIPD server to see if the
      package is already built. This also disables uploading the results, to
      avoid attempting to upload a duplicately-tagged package.
    * spec (ResolvedSpec) - The resolved spec to build.
    * version (str) - The symver (or 'latest') version of the package to build.

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
      '_3PP_TOOL_PLATFORM': spec.tool_platform,
      '_3PP_PACKAGE_NAME': spec.name,
      # CIPD uses 'mac' instead of 'darwin' for historical reasons.
      'GOOS': spec.platform.split('-')[0].replace('mac', 'darwin'),
      # CIPD encodes the GOARCH/GOARM pair of ('arm', '6') as 'armv6l'.
      # Since GOARCH=6 is the default, we don't need to specify it.
      'GOARCH': spec.platform.split('-')[1].replace('armv6l', 'arm'),
    }
    if spec.platform.startswith('mac-'):
      env['MACOSX_DEPLOYMENT_TARGET'] = '10.10'
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
      if force_build or not cipd_spec.check():
        # Otherwise, build it
        _build_impl(
          api, cipd_spec, is_latest, spec_lookup, force_build,
          (lambda spec, version: build_resolved_spec(
            api, spec_lookup, cache, force_build, spec, version)),
          spec, version)

      return set_cache(cipd_spec)


def _build_impl(api, cipd_spec, is_latest, spec_lookup, force_build, recurse_fn,
                spec, version):
  workdir = Workdir(api, spec, version)
  with api.context(env={'_3PP_VERSION': version}):
    api.file.ensure_directory('mkdir -p [workdir]', workdir.base)

    with api.step.nest('fetch sources'):
      source.fetch_source(
        api, workdir, spec, version, spec_lookup, recurse_fn)

    if spec.create_pb.HasField("build"):
      with api.step.nest('run installation'):
        build.run_installation(api, workdir, spec)
      installed_prefix = workdir.output_prefix
    else:
      installed_prefix = workdir.checkout

    # Package stage
    cipd_spec.build(installed_prefix,
                    Spec.Create.Package.InstallMode.Name(
                      spec.create_pb.package.install_mode),
                    spec.create_pb.package.version_file)

    if spec.create_pb.HasField("verify"):
      with api.step.nest('run test'):
        verify.run_test(api, workdir, spec, cipd_spec)

    if not force_build:
      with api.step.nest('do upload'):
        cipd_spec.ensure_uploaded(is_latest)
