# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import constants
from gae_libs import appengine_util
from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from waterfall.flake.regression_range_analysis_pipeline import (
    RegressionRangeAnalysisPipeline)

from waterfall.flake.regression_range_analysis_pipeline import (
    RegressionRangeAnalysisPipeline)


def _GetLowerAndUpperBoundCommitPositions(lower_bound, upper_bound):
  """Returns numerical lower and upper bounds according to user input.

    Takes the raw user input as strings for upper and lower bounds and
    determines a numerical (lower_bound, upper_bound) pair. If either lower or
    upper bound is '' (not specified), substitute it with the other to
    generate a single-point range.

  Args:
    lower_bound (str): A string representation of the lower bound commit
        position specified by the user. Can be '' if not specified.
    upper_bound (str): A string representation of the upper bound commit
        position. Can be '' if not specified.

  Returns:
    lower_bound (int), upper_bound (int): The numeric lower and upper bounds to
        pass to RegressionRangeAnalysisPipeline. Returns (None, None) if input
        lower/upper bounds are not specified.
  """
  if not lower_bound and not upper_bound:
    return None, None

  lower_bound = lower_bound if lower_bound else upper_bound
  upper_bound = upper_bound if upper_bound else lower_bound
  lower_bound = int(lower_bound)
  upper_bound = int(upper_bound)

  return min(lower_bound, upper_bound), max(lower_bound, upper_bound)


def _ValidateInput(lower_bound_commit_position, upper_bound_commit_position,
                   iterations_to_rerun):
  """Validates the user input field to ensure values are in the correct format.

  Args:
    lower_bound_commit_position (str): A string representation of the lower
        bound commit position. Can be '' if not specified by the user.
    upper_bound_commit_position (str): A string representation of the upper
        bound commit position. Can be '' if not specified by the user.
    iterations_to_rerun (str): A string representation of the number of times
        the test should be rerun according to the user.

  Returns:
    Boolean whether or not the input is valid.
  """
  if not lower_bound_commit_position and not upper_bound_commit_position:
    # At least one of lower or upper bound is required.
    return False

  if lower_bound_commit_position and not lower_bound_commit_position.isdigit():
    return False

  if upper_bound_commit_position and not upper_bound_commit_position.isdigit():
    return False

  return iterations_to_rerun.isdigit()


class AnalyzeRegressionRange(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  @token.VerifyXSRFToken()
  def HandlePost(self):
    lower_bound_commit_position = self.request.get(
        'lower_bound_commit_position', '').strip()
    upper_bound_commit_position = self.request.get(
        'upper_bound_commit_position', '').strip()
    urlsafe_analysis_key = self.request.get('key')
    iterations_to_rerun = self.request.get('iterations_to_rerun', '100').strip()

    if not _ValidateInput(lower_bound_commit_position,
                          upper_bound_commit_position,
                          iterations_to_rerun):
      return {
          'template': 'error.html',
          'data': {
              'error_message': 'Input format is invalid.',
          },
          'return_code': 400
      }

    lower_bound_commit_position = int(lower_bound_commit_position)
    upper_bound_commit_position = int(upper_bound_commit_position)
    iterations_to_rerun = int(iterations_to_rerun)
    analysis = ndb.Key(urlsafe=urlsafe_analysis_key).get()

    if not analysis:
      return {
          'template': 'error.html',
          'data': {
              'error_message': 'Flake analysis was deleted unexpectedly!',
          },
          'return_code': 400
      }

    lower_bound, upper_bound = _GetLowerAndUpperBoundCommitPositions(
        lower_bound_commit_position, upper_bound_commit_position)

    pipeline_job = RegressionRangeAnalysisPipeline(
        urlsafe_analysis_key, lower_bound, upper_bound,
        int(iterations_to_rerun))
    pipeline_job.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)

    return {
        'data': {
            'lower_bound_commit_position': lower_bound,
            'upper_bound_commit_position': upper_bound,
            'urlsafe_analysis_key': urlsafe_analysis_key,
            'iterations_to_rerun': iterations_to_rerun
        }
    }
