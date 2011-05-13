# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for chromium-status.

See http://dev.chromium.org/developers/how-tos/depottools/presubmit-scripts for
details on the presubmit API built into gcl.
"""


UNIT_TESTS = [
    'tests.main_test',
]


def CommonChecks(input_api, output_api):
  output = []

  def join(*args):
    return input_api.os_path.join(input_api.PresubmitLocalPath(), *args)

  import sys
  sys_path_backup = sys.path
  try:
    sys.path = [
        join('..', 'google_appengine'),
        join('..', 'google_appengine', 'lib'),
        join('..', 'google_appengine', 'lib', 'simplejson'),
    ] + sys.path
    output.extend(input_api.canned_checks.RunPylint(
        input_api,
        output_api))
  finally:
    sys.path = sys_path_backup

  output.extend(input_api.canned_checks.RunPythonUnitTests(
      input_api,
      output_api,
      UNIT_TESTS))
  return output


def CheckChangeOnUpload(input_api, output_api):
  return CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return CommonChecks(input_api, output_api)
