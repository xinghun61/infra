# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from findit_v2.services.analysis.compile_failure import compile_analysis_util
from findit_v2.services import projects


def AnalyzeCompileFailure(context, build, compile_steps):
  """Analyzes the compile failure.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.
    compile_steps (buildbucket step.proto): The failed compile steps.
  """
  if context.luci_project_name in projects.LUCI_PROJECTS:  # pragma: no cover.
    logging.error('Findit v2 is not ready yet')
    return

  if context.luci_project_name == 'chromium':
    logging.warning('Findit does not support chromium project in v2.')
    return

  project_api = projects.GetProjectAPI(context.luci_project_name)
  assert project_api, 'Unsupported project {}'.format(context.luci_project_name)

  # Reads detailed compile failures and saves information in data store.
  detailed_compile_failures = project_api.GetCompileFailures(
      build, compile_steps)

  # Updates detailed_compile_failures for first failures.
  compile_analysis_util.DetectFirstFailures(context, build,
                                            detailed_compile_failures)
  # TODO(crbug.com/949836): Look for existing failure groups.
  compile_analysis_util.SaveCompileFailures(context, build,
                                            detailed_compile_failures)

  first_failures_in_current_build = (
      compile_analysis_util.GetFirstFailuresInCurrentBuild(
          context, build, detailed_compile_failures))

  if not first_failures_in_current_build['failures']:
    # No first time failures in current build. No need for a new analysis.
    return

  compile_analysis_util.SaveCompileAnalysis(context, build,
                                            first_failures_in_current_build)
