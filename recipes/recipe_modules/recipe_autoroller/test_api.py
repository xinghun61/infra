# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from recipe_engine import recipe_test_api


class RecipeAutorollerTestApi(recipe_test_api.RecipeTestApi):
  _TBR_EMAILS = ('foo@bar.example.com', 'meep@example.com')
  _EXTRA_REVIEWERS = ('foo@chromium.org', 'foo@bar.example.com',
                      'meep@example.com')

  def repo_spec(self, tbr_emails=_TBR_EMAILS, extra_reviewers=_EXTRA_REVIEWERS,
                disable_reason='', trivial_commit=True, trivial_dryrun=False,
                nontrivial_dryrun=True, include_autoroll_options=True):
    spec = {
      'api_version': 2,
      'deps': {
        'recipe_engine': {},
      },
    }
    if include_autoroll_options:
      spec['autoroll_recipe_options'] = {
        'trivial': {
          'tbr_emails': list(tbr_emails),
          'automatic_commit': trivial_commit,
          'dry_run': trivial_dryrun,
        },
        'nontrivial': {
          'extra_reviewer_emails': list(extra_reviewers),
          'automatic_commit_dry_run': nontrivial_dryrun,
        },
        'disable_reason': disable_reason,
      }
    return spec

  def roll_data(self, project, spec=None, success=True, trivial=True,
                empty=False):
    """Returns mock roll and recipes.cfg data for |project|."""
    if spec is None:
      spec = self.repo_spec()
    if empty:
      success = False

    ret = self.empty_test_data() + self.recipe_cfg(project, spec)
    if spec.get('autoroll_recipe_options', {}).get('disable_reason'):
      return ret

    picked_roll_details = {
      'commit_infos': {
        'recipe_engine': [
          {
            'author_email': 'foo@chromium.org',
            'message_lines': [
              'some commit message',
              'R=bar@chromium.org,baz@chromium.org,invalid1,invalid2@chromium',
              'BUG=123,456',
            ],
            'revision': '123abc',
          },
        ],
      },
      'spec': spec,
    }

    roll_result = {
      'success': success,
      'trivial': trivial if success else None,
      'picked_roll_details': picked_roll_details if success else None,
    }
    roll_result['rejected_candidates_count'] = 0
    if empty:
      roll_result['roll_details'] = []
    else:
      roll_result['roll_details'] = [picked_roll_details]
      if not success:
        roll_result['rejected_candidates_count'] = 1

    ret += self.step_data('%s.roll' % project, self.m.json.output(roll_result))
    return ret

  def repo_data(self, project, trivial, status, timestamp):
    return (
      self.override_step_data(
        '%s.gsutil repo_state' % project,
        self.m.raw_io.stream_output(
          json.dumps({
            'issue': '123456789',
            'issue_url': 'https://codereview.chromium.org/123456789',
            'trivial': trivial,
            'last_roll_ts_utc': timestamp,
          }),
          stream='stdout'),
        self.m.raw_io.stream_output('', stream='stderr')) +
      self.step_data('%s.git cl status' % project,
                     self.m.raw_io.stream_output(status)))

  def recipe_cfg(self, project, spec=None):
    """Returns mock recipes.cfg data (only) for |project|.

    This is used for tests which abort between the 'read recipes.cfg' step and
    the 'roll' step (e.g. which read repo state and decide to quit early).

    For "normal" test runs, you'll want to use roll_data() from this
    RecipeTestApi, which includes this step data automatically.
    """
    if spec is None:
      spec = self.repo_spec()
    return self.override_step_data(
      '%s.read recipes.cfg' % project, self.m.json.output(spec)
    )
