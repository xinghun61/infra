# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from recipe_engine import recipe_test_api


class RecipeAutorollerTestApi(recipe_test_api.RecipeTestApi):
  _TBR_EMAILS = ('foo@bar.example.com', 'meep@example.com')
  _EXTRA_REVIEWERS = ('foo@chromium.org', 'foo@bar.example.com',
                      'meep@example.com')

  def _autoroll_recipe_options(self, tbr_emails, extra_reviewers,
                               disable_reason, trivial_commit,
                               nontrivial_dryrun):
    return {
      'disable_reason': disable_reason,
      'trivial': {
        'tbr_emails': list(tbr_emails),
        'automatic_commit': trivial_commit,
      },
      'nontrivial': {
        'extra_reviewers': list(extra_reviewers),
        'automatic_commit_dry_run': nontrivial_dryrun,
      },
    }

  def roll_data(self, project, success=True, trivial=True, empty=False,
                tbr_emails=_TBR_EMAILS, extra_reviewers=_EXTRA_REVIEWERS,
                disable_reason='', trivial_commit=True, nontrivial_dryrun=True):
    """Returns mock roll and recipes.cfg data for |project|."""
    if empty:
      success = False

    ret = self.empty_test_data()

    autoroll_recipe_options = self._autoroll_recipe_options(
      tbr_emails, extra_reviewers, disable_reason, trivial_commit,
      nontrivial_dryrun)

    ret += self.override_step_data(
      '%s.read recipes.cfg' % project,
      self.m.json.output({
        'autoroll_recipe_options': autoroll_recipe_options,
      })
    )
    if disable_reason:
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
      'spec': {
        'api_version': 2,
        'deps': {
          'recipe_engine': {},
        },
        'autoroll_recipe_options': autoroll_recipe_options,
      },
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

  def recipe_cfg(self, project, tbr_emails=_TBR_EMAILS,
                 extra_reviewers=_EXTRA_REVIEWERS, disable_reason='',
                 trivial_commit=True, nontrivial_dryrun=True):
    """Returns mock recipes.cfg data (only) for |project|.

    This is used for tests which abort between the 'read recipes.cfg' step and
    the 'roll' step (e.g. which read repo state and decide to quit early).

    For "normal" test runs, you'll want to use roll_data() from this
    RecipeTestApi, which includes this step data automatically.
    """
    return self.override_step_data(
      '%s.read recipes.cfg' % project,
      self.m.json.output({
        'autoroll_recipe_options': self._autoroll_recipe_options(
          tbr_emails, extra_reviewers, disable_reason, trivial_commit,
          nontrivial_dryrun),
      })
    )
