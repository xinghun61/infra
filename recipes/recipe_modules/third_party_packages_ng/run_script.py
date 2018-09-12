# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Defines the utility function for running a script; understands how to run
bash scripts on all host platforms (including windows)."""


def run_script(api, *args, **kwargs):
  """Runs a script (python or bash) with the given arguments.

  Understands how to make bash scripts run on windows.

  The script name (`args[0]`) must end with either '.sh' or '.py'.
  """
  script_name = args[0].pieces[-1]
  step_name = str(' '.join([script_name]+map(str, args[1:])))

  if script_name.endswith('.sh'):
    cmd = ['bash'] + list(args)

    # On windows, we use the bash.exe that ships with git-for-windows,
    # cheating a bit by injecting a `git-bash` script into $PATH, and then
    # running the desired script with `git bash` instead of `bash`.
    env_prefixes={}
    if api.platform.is_win:
      env_prefixes['PATH'] = [
        api.third_party_packages_ng.resource('win_support')]
      cmd = ['git'] + cmd

    with api.context(env_prefixes=env_prefixes):
      return api.step(step_name, cmd, **kwargs)

  elif script_name.endswith('.py'):
    return api.python(step_name, args[0], args[1:], **kwargs)

  else: # pragma: no cover
    assert False, 'scriptname must end with either ".sh" or ".py"'
