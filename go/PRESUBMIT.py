# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Presubmit script for Go code.

Verifies all files are properly formatted.
"""


def GoFmtChecks(input_api, output_api):  # pragma: no cover
  # Grab a list of modified *.go files.
  affected_files = sorted([
    f.AbsoluteLocalPath()
    for f in input_api.AffectedFiles(include_deletes=False)
    if f.AbsoluteLocalPath().endswith('.go')
  ])
  if not affected_files:
    return []

  if input_api.is_committing:
    error_type = output_api.PresubmitError
  else:
    error_type = output_api.PresubmitPromptWarning

  def join(*p):
    return input_api.os_path.join(input_api.PresubmitLocalPath(), *p)

  # Wrap check_gofmt.py invocation with env.py to make 'gofmt' available
  # in PATH. It will also bootstrap Go dev environment if necessary. Don't
  # forget to explicitly call python for Windows' sake.
  cmd = [
    input_api.python_executable,
    join('env.py'),
    input_api.python_executable,
    join('check_gofmt.py'),
  ]
  if input_api.verbose:
    cmd.append('--verbose')

  return [
    input_api.Command(
        name='Check gofmt (%d files)' % len(affected_files),
        cmd=cmd,
        kwargs={'stdin': '\n'.join(affected_files)},
        message=error_type),
  ]


def CommonChecks(input_api, output_api):  # pragma: no cover
  tests = GoFmtChecks(input_api, output_api)
  return input_api.RunTests(tests)


def CheckChangeOnUpload(input_api, output_api):  # pragma: no cover
  return CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):  # pragma: no cover
  output = CommonChecks(input_api, output_api)
  return output
