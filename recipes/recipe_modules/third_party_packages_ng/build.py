# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import run_script

def run_installation(api, workdir, spec):
  """Actually runs build phase of the given `spec` within the provided
  `workdir`.

  This function knows how to install the cross-compiler toolchain into the
  environment (if needed for the spec's target platform).

  Args:
    * api - The ThirdPartyPackagesNGApi's `self.m` module collection.
    * workdir (Workdir) - The working directory object we're going to build the
      spec in. This function will create the output in `workdir.output_prefix`.
    * spec (ResolvedSpec) - The spec to build.
  """
  my_args = [workdir.output_prefix, workdir.deps_prefix]
  if spec.create_pb.build.install:
    script = spec.create_pb.build.install[0]
    rest = spec.create_pb.build.install[1:] + my_args
  else:
    script = "install.sh"
    rest = my_args

  script_path = workdir.script_dir(spec.name).join(script)

  env_prefixes = {'PATH': [workdir.tools_prefix]}
  with api.context(cwd=workdir.checkout, env_prefixes=env_prefixes):
    # TODO(iannucci): Actually just build toolchains (in 3pp) to run natively
    # on all the different platforms, instead of relying on dockcross.
    # TODO(iannucci): Add options to configure toolchain in 3pp.pb, e.g. to
    # use clang instead of gcc, etc. Alternately, if we just build the cross
    # compiler toolchains correctly as in the above TODO, we can just use the
    # 'tool' mechanism.
    if spec.platform.startswith('linux-'):
      # dockerbuild platform names are different from CIPD's name for them.
      dockerbuild_platform = {
        'linux-armv6l': 'linux-armv6',
        'linux-armv64': 'linux-armv64',
        'linux-mips32': 'linux-mipsel',
        'linux-mips64': 'linux-mips64',
        'linux-amd64': 'manylinux-x64',
        'linux-386': 'manylinux-x86',
      }[spec.platform]

      interpreter = {
        'py': 'python',
        'sh': 'bash',
      }[script.rsplit('.', 1)[-1]]

      cmd = [
        'infra.tools.dockerbuild', 'run', '--platform', dockerbuild_platform,
        '--workdir', workdir.base,
      ]

      env_args = [
        ('--env-prefix', k, str(v))
        for k, vs in api.context.env_prefixes.iteritems()
        for v in vs
      ] + [
        ('--env-suffix', k, str(v))
        for k, vs in api.context.env_suffixes.iteritems()
        for v in vs
      ] + [
        ('--env', k, str(v))
        for k, v in api.context.env.iteritems()
      ]
      for tup in env_args:
        cmd.extend(tup)

      cmd += ['--', interpreter, script_path] + rest

      api.python('do install',
        api.third_party_packages_ng.package_repo_resource('run.py'), cmd)
      return

    if spec.platform.startswith('mac-'):
      ctx = api.osx_sdk('mac')
    elif spec.platform.startswith('windows-'):
      ctx = api.windows_sdk()
    else:  # pragma: no cover
      assert False, (
        'Do not know which toolchain to use for %r' % (spec.platform,))

    with ctx:
      run_script.run_script(api, script_path, *rest)
