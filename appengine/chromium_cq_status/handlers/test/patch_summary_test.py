# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import logging
import os

from third_party.testing_utils import testing

import main
from model.record import Record


class PatchSummaryTest(testing.AppengineTestCase):
  app_module = main.app

  def test_patch_summary_simple(self):
    return self._test_patch('simple')

  def test_patch_summary_flaky(self):
    return self._test_patch('flaky')

  def test_no_verifier_start(self):
    return self._test_patch('no_verifier_start')

  def test_no_verifier_start_explicit_codereview(self):
    return self._test_patch(
        'no_verifier_start', codereview_hostname='codereview.chromium.org')

  def test_patch_summary_simple_v2(self):
    return self._test_patch(
        'simple', codereview_hostname='codereview.chromium.org')

  def test_patch_summary_flaky_v2(self):
    return self._test_patch(
        'flaky', codereview_hostname='codereview.chromium.org')

  def test_no_verifier_start_v2(self):
    return self._test_patch(
        'no_verifier_start',
        codereview_hostname='chromium-review.googlesource.com')

  # TODO(sergeyberezin): add a small real-life CL for an integration
  # test.

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

  def _test_patch(self, name, issue=123456789, codereview_hostname=None):
    self._load_records('patch_%s.json' % name)
    if not codereview_hostname:
      response = self.test_app.get('/patch-summary/%s/1' % issue)
    else:
      response = self.test_app.get('/v2/patch-summary/%s/%s/1' %
                                   (codereview_hostname, issue))
    summary = json.loads(response.body)
    logging.debug(json.dumps(summary, indent=2))
    return summary


def _load_json(filename):
  path = os.path.join(os.path.dirname(__file__), 'resources', filename)
  return json.loads(open(path).read())
