# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for chromium-build.

See http://dev.chromium.org/developers/how-tos/depottools/presubmit-scripts for
details on the presubmit API built into gcl.

Setup instructions:
  sudo easy_install nose nosegae WebTest
  sudo aptitude install python-mysqldb  # Resolves the 'The rdbms API is not
                                        # available' warning.
  download GAE SDK to ../google_appengine/
  git cl presubmit

To run the tests directly:
  export PYTHONPATH="../google_appengine/"
  nosetests --with-gae --gae-lib-root=../google_appengine/

To interact with the environment:
  (insert a line: import code; code.interact(locals=local()))
  export PYTHONPATH="../google_appengine/"
  nosetests --with-gae --gae-lib-root=../google_appengine/ -s
"""


import sys


def CommonChecks(input_api, output_api):
  # We don't want to hinder users from uploading incomplete patches.
  if input_api.is_committing:
    message_type = output_api.PresubmitError
  else:
    message_type = output_api.PresubmitNotifyResult
  results = []

  # Find the GAE SDK starting at the PRESUBMIT.py's parent directory.
  previous_dir = ''
  sdk_path = ''
  base_dir = input_api.PresubmitLocalPath()
  while base_dir != previous_dir:
    previous_dir = base_dir
    sdk_path = input_api.os_path.join(base_dir, 'google_appengine')
    if not input_api.os_path.isfile(
        input_api.os_path.join(sdk_path, 'VERSION')):
      sdk_path = ''
      base_dir = input_api.os_path.dirname(base_dir)

  if len(sdk_path) == 0:
    results.append(message_type(
        'tests failed, could not find google_appengine SDK'))
    return results

  env = input_api.environ.copy()
  env['PYTHONPATH'] = input_api.os_path.join(sdk_path,
                                             env.get('PYTHONPATH', ''))
  cmd = ['nosetests', '--with-gae', '--gae-lib-root=%s' % sdk_path]
  try:
    input_api.subprocess.check_output(cmd, stderr=input_api.subprocess.STDOUT,
        env=env)
  except (OSError, input_api.subprocess.CalledProcessError), e:
    results.append(message_type('nosetests failed!\n%s' % (e)))

  # Run PyLint checks.
  backup_sys_path = sys.path
  try:
    black_list = list(input_api.DEFAULT_BLACK_LIST)
    sys.path = [
        sdk_path,
        input_api.os_path.join(sdk_path, 'lib'),
        input_api.os_path.join(sdk_path, 'lib', 'simplejson'),
    ] + sys.path
    # Update our environment to include the standard modules in AppEngine.
    import appcfg
    appcfg.fix_sys_path()
    disabled_warnings = [
        'W0232',  # has no init, disabled due to webapp2
    ]
    results.extend(input_api.canned_checks.RunPylint(
        input_api,
        output_api,
        black_list=black_list,
        disabled_warnings=disabled_warnings))
  finally:
    sys.path = backup_sys_path
  return results


def CheckChangeOnUpload(input_api, output_api):
  return CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return CommonChecks(input_api, output_api)
