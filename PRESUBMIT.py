# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for buildbot.

See http://dev.chromium.org/developers/how-tos/depottools/presubmit-scripts for
details on the presubmit API built into gcl.
"""


DISABLED_TESTS = [
    '.*appengine/chromium_status/tests/main_test.py',
    '.*appengine/chromium_build/app_test.py',
]


DISABLED_PROJECTS = [
    'appengine/chromium_build',
    'infra/services/lkgr_finder',
    'infra/services/gnumbd',
]


def CommonChecks(input_api, output_api):
  tests = []

  blacklist = list(input_api.DEFAULT_BLACK_LIST) + DISABLED_PROJECTS

  status_output = input_api.subprocess.check_output(
      ['git', 'status', '--porcelain', '--ignored'])
  statuses = [(line[:2], line[3:]) for line in status_output.splitlines()]
  ignored_files = [path for (mode, path) in statuses if mode in ('!!', '??')]

  blacklist = blacklist + ignored_files

  disabled_warnings = [
    'W0231',  # __init__ method from base class is not called
    'W0232',  # Class has no __init__ method
    'W0613',  # Unused argument
    'F0401',  # Unable to import
  ]
  appengine_path = input_api.os_path.abspath(
      input_api.os_path.join(
          input_api.os_path.dirname(input_api.PresubmitLocalPath()),
          'google_appengine'))
  tests.extend(input_api.canned_checks.GetPylint(
      input_api,
      output_api,
      black_list=blacklist,
      disabled_warnings=disabled_warnings,
      extra_paths_list=[appengine_path]))

  whitelist = [r'.+_test\.py$']
  blacklist = blacklist + DISABLED_TESTS
  tests.extend(input_api.canned_checks.GetUnitTestsRecursively(
      input_api, output_api, '.', whitelist=whitelist, blacklist=blacklist))

  # Run the tests.
  return input_api.RunTests(tests)


def CheckChangeOnUpload(input_api, output_api):
  return CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  output = CommonChecks(input_api, output_api)
  output.extend(input_api.canned_checks.CheckOwners(input_api, output_api))
  return output
