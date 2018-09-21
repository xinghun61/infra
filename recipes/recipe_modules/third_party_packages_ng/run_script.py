# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Defines the utility function for running a script; understands how to run
bash scripts on all host platforms (including windows)."""

from contextlib import contextmanager

from .workdir import Workdir

def _extract_contextual_dockerbuild_env_args(api):
  return [
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

# Dockerbuild uses different names than the CIPD platform names. This maps from
# the CIPD platform name to the dockerbuild name.
_DOCKERBUILD_PLATFORM = {
  'linux-armv6l': 'linux-armv6',
  'linux-arm64': 'linux-arm64',
  'linux-mips32': 'linux-mipsel',
  'linux-mips64': 'linux-mips64',
  'linux-amd64': 'manylinux-x64',
  'linux-386': 'manylinux-x86',
}

def run_script(api, *args, **kwargs):
  """Runs a script (python or bash) with the given arguments.

  Understands how to make bash scripts run on windows, as well as how to run
  linux commands under dockerbuild.

  Will prepare the windows or OS X toolchain as well.

  Args:
    * args (*str) - The arguments of the script. The script name (`args[0]`)
      must end with either '.sh' or '.py'.

  Kwargs:
    * compile_platform (str) - Indicates what platform we want this step to
      compile for. If omitted, executes under the host platform without any
      compiler available.
    * workdir (Workdir) - The working directory object we're running the script
      under. Required if `compile_platform` is specified.
    * stdout - Passed through to the underlying step.
    * step_test_data - Passed through to the underlying step.
  """
  compile_platform = kwargs.pop('compile_platform', '')
  workdir = kwargs.pop('workdir', None)
  stdout = kwargs.pop('stdout', None)
  step_test_data = kwargs.pop('step_test_data', None)

  if compile_platform:
    assert isinstance(workdir, Workdir), (
        'workdir argument required if compile_platform is specified')

  script_name = args[0].pieces[-1]
  step_name = str(' '.join([script_name]+map(str, args[1:])))

  interpreter = {
    'py': 'python',
    'sh': 'bash',
  }.get(script_name.rsplit('.', 1)[-1], None)
  assert interpreter is not None, (
      'scriptname must end with either ".sh" or ".py"')

  # TODO(iannucci): Allow better control of toolchain environments.
  # See also resolved_spec.tool_platform.
  if compile_platform.startswith('linux-'):
    # dockerbuild time.
    dockerbuild_platform = _DOCKERBUILD_PLATFORM[compile_platform]
    cmd = [
      'infra.tools.dockerbuild', 'run', '--platform', dockerbuild_platform,
      '--workdir', workdir.base,
    ]
    for tup in _extract_contextual_dockerbuild_env_args(api):
      cmd.extend(tup)
    cmd += ['--', interpreter, args[0]] + list(args[1:])
    return api.python(step_name,
        api.third_party_packages_ng.package_repo_resource('run.py'), cmd,
        stdout=stdout, step_test_data=step_test_data)

  @contextmanager
  def no_sdk():
    yield
  sdk = no_sdk()
  if compile_platform.startswith('mac-'):
    sdk = api.osx_sdk('mac')
  elif compile_platform.startswith('windows-'):
    sdk = api.windows_sdk()

  with sdk:
    if interpreter == 'bash':
      cmd = ['bash'] + list(args)

      # On windows, we use the bash.exe that ships with git-for-windows,
      # cheating a bit by injecting a `git-bash` script into $PATH, and then
      # running the desired script with `git bash` instead of `bash`.
      env_prefixes = {}
      if api.platform.is_win:
        env_prefixes['PATH'] = [
          api.third_party_packages_ng.resource('win_support')]
        cmd = ['git'] + cmd
      elif api.platform.is_mac:
        env_prefixes['PATH'] = [
          api.third_party_packages_ng.resource('mac_support')]

      with api.context(env_prefixes=env_prefixes):
        return api.step(step_name, cmd,
                        stdout=stdout, step_test_data=step_test_data)

    elif interpreter == 'python':
      return api.python(step_name, args[0], args[1:],
                        stdout=stdout, step_test_data=step_test_data)

    assert False, 'impossible'  # pragma: no cover
