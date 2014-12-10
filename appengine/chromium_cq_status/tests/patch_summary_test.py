# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import logging
import os

from tests.testing_utils import testing

import main
from model.record import Record


class PatchSummaryTest(testing.AppengineTestCase):
  app_module = main.app

  def test_patch_summary_simple(self):
    return self._test_patch('simple')

  def test_patch_summary_flaky(self):
    return self._test_patch('flaky')

  # https://chromium-cq-status.appspot.com/recent#issue=754513002,patchset=1
  def test_patch_summary_754513002_1(self):
    return self._test_patch('754513002_1', 754513002)

  # https://chromium-cq-status.appspot.com/recent#issue=765763002,patchset=1
  def test_patch_summary_765763002_1(self):
    return self._test_patch('765763002_1', 765763002)

  def _load_records(self, filename):
    assert Record.query().count() == 0
    records = _load_json(filename)
    for record in records:
      self.mock_now(datetime.utcfromtimestamp(record['timestamp']))
      Record(
        id=record['key'],
        tags=record['tags'],
        fields=record['fields'],
      ).put()

  def _test_patch(self, name, issue=123456789):
    self._load_records('patch_%s.json' % name)
    response = self.test_app.get('/patch-summary/%s/1' % issue)
    summary = json.loads(response.body)
    logging.debug(json.dumps(summary, indent=2))
    return summary


def _load_json(filename):
  path = os.path.join(os.path.dirname(__file__), 'resources', filename)
  return json.loads(open(path).read())
