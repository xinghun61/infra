# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from recipe_engine import recipe_test_api


class RecipeAutorollerTestApi(recipe_test_api.RecipeTestApi):
  def roll_data(self, project, success=True, trivial=True, empty=False):
    """Returns mock roll data for |project|."""
    if empty:
      success = False

    ret = self.empty_test_data()

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
        'deps': {},
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
    return (self.override_step_data('%s.gsutil repo_state' % project,
          self.m.raw_io.stream_output(json.dumps(
              {
                'issue': '123456789',
                'issue_url': 'https://codereview.chromium.org/123456789',
                'trivial': trivial,
                'last_roll_ts_utc': timestamp,
              }),
              stream='stdout'),
          self.m.raw_io.stream_output('', stream='stderr')) +
        self.step_data('%s.git cl status' % project,
            self.m.raw_io.stream_output(status)))
