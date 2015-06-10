# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Presubmit script for Go code."""


def CommandInEnv(input_api, output_api, name, cmd, kwargs):  # pragma: no cover
  """Returns input_api.Command that wraps |cmd| with invocation to env.py.

  env.py makes golang tools available in PATH. It also bootstraps Golang dev
  environment if necessary.
  """
  if input_api.is_committing:
    error_type = output_api.PresubmitError
  else:
    error_type = output_api.PresubmitPromptWarning
  full_cmd = [
    input_api.python_executable,
    input_api.os_path.join(input_api.PresubmitLocalPath(), 'env.py'),
  ]
  full_cmd.extend(cmd)
  return input_api.Command(
      name=name,
      cmd=full_cmd,
      kwargs=kwargs,
      message=error_type)


def Checker(tool_name, input_api, output_api):
  affected_files = sorted([
    f.AbsoluteLocalPath()
    for f in input_api.AffectedFiles(include_deletes=False)
    if f.AbsoluteLocalPath().endswith('.go')
  ])
  if not affected_files:
    return []
  cmd= [
    input_api.python_executable,
    input_api.os_path.join(input_api.PresubmitLocalPath(), 'check.py'),
    tool_name,
  ]
  if input_api.verbose:
    cmd.append("--verbose")
  return [
    CommandInEnv(
        input_api, output_api,
        name='Check %s (%d files)' % (tool_name, len(affected_files)),
        cmd=cmd,
        kwargs={'stdin': '\n'.join(affected_files)}),
  ]


def CommonChecks(input_api, output_api):  # pragma: no cover
  tests = []
  tests.extend(Checker("gofmt", input_api, output_api))
  tests.extend(Checker("govet", input_api, output_api))
  tests.extend(Checker("golint", input_api, output_api))
  return input_api.RunTests(tests)


def CheckChangeOnUpload(input_api, output_api):  # pragma: no cover
  return CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):  # pragma: no cover
  output = CommonChecks(input_api, output_api)
  return output
