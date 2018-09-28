# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Logic to run testing script on the built CIPD package."""

from .run_script import run_script

def run_test(api, workdir, spec, cipd_spec):
  """Runs the test in the Verify message on the CIPD package.

  Args:
    * workdir (Workdir) - The directories that we're currently operating within.
    * spec (ResolvedSpec) - The spec for the package we're testing.
    * cipd_spec (CIPDSpec) - The package we've already built and want to test.
  """
  api.file.ensure_directory('mkdir [verify]', workdir.verify)
  test_pkg = workdir.verify.join('cipd.pkg')
  api.file.copy('cp cipd.pkg [verify]/cipd.pkg',
                cipd_spec.local_pkg_path(), test_pkg)

  # TODO(iannucci): allow better control of toolchain environments.
  env_prefixes = {}
  if spec.platform.startswith('linux-'):
    # We're going to use dockcross, so make sure there's a compatible version of
    # cipd in $PATH.
    api.file.ensure_directory('mkdir [bin_tools]', workdir.bin_tools)
    # TODO(iannucci): This is a bit gross; we should have a way to copy the
    # CIPD/vpython versions (as a tag not an instance ID) from the environment
    # for use here.
    api.cipd.ensure(
      workdir.bin_tools,
      (api.cipd.EnsureFile().
       add_package(
         'infra/tools/cipd/%s' % spec.tool_platform, 'latest').
       add_package(
         'infra/tools/luci/vpython/%s' % spec.tool_platform, 'latest')
       ))
    env_prefixes = {'PATH': [workdir.bin_tools]}

  script = spec.create_pb.verify.test[0]
  rest = spec.create_pb.verify.test[1:] + [test_pkg]
  with api.context(cwd=workdir.verify, env_prefixes=env_prefixes):
    run_script(
      api, workdir.script_dir(spec.name).join(script), *rest,
      compile_platform=spec.platform, workdir=workdir)
