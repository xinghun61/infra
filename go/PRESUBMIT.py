# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Presubmit script for Go code."""


def GetAffectedGoFiles(input_api, include_deletes=False):  # pragma: no cover
  """Returns a list of absolute paths to modified *.go files."""
  return sorted([
    f.AbsoluteLocalPath()
    for f in input_api.AffectedFiles(include_deletes=include_deletes)
    if f.AbsoluteLocalPath().endswith('.go')
  ])


def GetAffectedGoPackages(input_api):  # pragma: no cover
  """Returns a list of Go packages (under src/) affected by the CL.

  Changes to subpackages are not considered as changes to parent package, e.g.
  a change to infra/libs/gce/*.go means that ONLY infra/libs/gce package
  changed, but not infra/libs.
  """
  packages = set()
  src_root = input_api.os_path.join(input_api.PresubmitLocalPath(), 'src')
  for path in GetAffectedGoFiles(input_api, include_deletes=True):
    rel = input_api.os_path.relpath(input_api.os_path.dirname(path), src_root)
    if rel[:2] != '..':
      packages.add(rel)

  # Exclude packages that were removed entirely.
  for pkg in list(packages):
    path = input_api.os_path.join(src_root, pkg)
    if not input_api.os_path.exists(path):
      packages.discard(pkg)

  # Go package paths use '/'.
  return sorted(x.replace('\\', '/') for x in packages)


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


def GoFmtChecks(input_api, output_api):  # pragma: no cover
  affected_files = GetAffectedGoFiles(input_api)
  if not affected_files:
    return []
  cmd = [
    input_api.python_executable,
    input_api.os_path.join(input_api.PresubmitLocalPath(), 'check_gofmt.py')
  ]
  if input_api.verbose:
    cmd.append('--verbose')
  return [
    CommandInEnv(
        input_api, output_api,
        name='Check gofmt (%d files)' % len(affected_files),
        cmd=cmd,
        kwargs={'stdin': '\n'.join(affected_files)}),
  ]


def GoVetChecks(input_api, output_api):  # pragma: no cover
  return [
    CommandInEnv(
        input_api, output_api,
        name='Check go vet %s' % pkg,
        cmd=['go', 'vet', pkg],
        kwargs={})
    for pkg in GetAffectedGoPackages(input_api)
  ]


def CommonChecks(input_api, output_api):  # pragma: no cover
  tests = []
  tests.extend(GoFmtChecks(input_api, output_api))
  tests.extend(GoVetChecks(input_api, output_api))
  return input_api.RunTests(tests)


def CheckChangeOnUpload(input_api, output_api):  # pragma: no cover
  return CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):  # pragma: no cover
  output = CommonChecks(input_api, output_api)
  return output
