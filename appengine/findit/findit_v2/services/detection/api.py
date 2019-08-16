# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from findit_v2.services import build_util
from findit_v2.services import constants
from findit_v2.services.analysis.compile_failure import compile_analysis
from findit_v2.services.analysis.test_failure import test_analysis
from findit_v2.services.failure_type import StepTypeEnum


def OnBuildFailure(context, build):
  """Processes the failed build within the given context.

  If the failures are supported by Findit, an analysis will start.

  Args:
    context (findit_v2.services.context.Context): Scope of the analysis.
    build (buildbucket build.proto): ALL info about the build.

  Returns:
    True if the failed build is supported and analyzed; otherwise False.
  """
  logging.info('Context of analysis: %r', context)
  logging.info('Failed build is: %r', build.id)

  failed_steps = build_util.GetFailedStepsInBuild(context, build)

  if not failed_steps:
    logging.debug('No failed steps found for failed build %d', build.id)
    return False

  compile_steps = [
      fs[0] for fs in failed_steps if fs[1] == StepTypeEnum.COMPILE
  ]
  if compile_steps:
    logging.info('Compile failure found in build %d.', build.id)
    return compile_analysis.AnalyzeCompileFailure(context, build, compile_steps)

  test_steps = [
    fs[0] for fs in failed_steps if fs[1] == StepTypeEnum.TEST
  ]
  if test_steps:
    logging.info('Test failure found in build %d.', build.id)
    return test_analysis.AnalyzeTestFailure(context, build, test_steps)

  logging.info('Unsupported failure types: %r', [fs[1] for fs in failed_steps])
  return False


def OnRerunBuildCompletion(context, rerun_build):
  """Processes the completed rerun build within the given context.

   Args:
     context (findit_v2.services.context.Context): Scope of the analysis.
     rerun_build (buildbucket build.proto): ALL info about the rerun build.

   Returns:
     True if the rerun build completes with SUCCESS or FAILURE status, otherwise
     False.
   """
  logging.info('Context of analysis: %r', context)
  logging.info('Rerun build is: %r', rerun_build.id)

  purpose_tag = None
  for tag in rerun_build.tags:
    if tag.key == constants.RERUN_BUILD_PURPOSE_TAG_KEY:
      purpose_tag = tag.value

  if not purpose_tag:
    logging.error('No purpose tag set for rerun build %d', rerun_build.id)
    return False

  if purpose_tag == constants.COMPILE_RERUN_BUILD_PURPOSE:
    # The rerun build is for a compile failure analysis.
    return compile_analysis.OnCompileRerunBuildCompletion(context, rerun_build)

  if purpose_tag == constants.TEST_RERUN_BUILD_PURPOSE:
    # The rerun build is for a test failure analysis.
    return test_analysis.OnTestRerunBuildCompletion(context, rerun_build)

  logging.info('Rerun build %d with unsupported purpose %s.', rerun_build.id,
               purpose_tag)
  return False
