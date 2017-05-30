# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission


def _GetLowerAndUpperBoundCommitPositions(lower_bound, upper_bound):
  if lower_bound is None and upper_bound is None:
    return None, None

  lower_bound = lower_bound if lower_bound is not None else upper_bound
  upper_bound = upper_bound if upper_bound is not None else lower_bound

  return min(lower_bound, upper_bound), max(lower_bound, upper_bound)


def _ValidateInput(lower_bound_commit_position, upper_bound_commit_position,
                   iterations_to_rerun):
  if (lower_bound_commit_position is None and
      upper_bound_commit_position is None):
    return False

  try:
    if lower_bound_commit_position is not None:
      lower_bound_commit_position = int(lower_bound_commit_position)
    if upper_bound_commit_position is not None:
      upper_bound_commit_position = int(upper_bound_commit_position)
    iterations_to_rerun = int(iterations_to_rerun)
    return True
  except ValueError:
    return False


class AnalyzeRegressionRange(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):
    return self.HandlePost()

  def HandlePost(self):
    lower_bound_commit_position = self.request.get(
        'lower_bound_commit_position')
    upper_bound_commit_position = self.request.get(
        'upper_bound_commit_position')
    urlsafe_analysis_key = self.request.get('key')
    iterations_to_rerun = self.request.get('iterations_to_rerun')

    if not _ValidateInput(lower_bound_commit_position,
                          upper_bound_commit_position,
                          iterations_to_rerun):  # pragma: no cover
      return {
          'template': 'error.html',
          'data': {
              'error_message': 'Input format is invalid.',
          },
          'return_code': 400
      }

    analysis = ndb.Key(urlsafe=urlsafe_analysis_key).get()

    if not analysis:  # pragma: no cover
      return {
          'template': 'error.html',
          'data': {
              'error_message': 'Flake analysis was deleted unexpectedly!',
          },
          'return_code': 400
      }

    lower_bound, upper_bound = _GetLowerAndUpperBoundCommitPositions(
        lower_bound_commit_position, upper_bound_commit_position)

    # TODO(lijeffrey): Convert lower/upper bound commit positions to build
    # numbers and pass to recursive_flake_pipeline.
    return {
        'data': {
            'lower_bound_commit_position': lower_bound,
            'upper_bound_commit_position': upper_bound,
            'urlsafe_analysis_key': urlsafe_analysis_key,
            'iterations_to_rerun': iterations_to_rerun
        }
    }
