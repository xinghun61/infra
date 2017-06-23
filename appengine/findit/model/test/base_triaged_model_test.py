# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from model.base_triaged_model import TriagedModel
from model.base_triaged_model import TriageResult
from waterfall.test import wf_testcase


class _DummyModel(TriagedModel):
  completed = True


class TriagedModelTest(wf_testcase.WaterfallTestCase):

  def testUpdateTriageResult(self):
    triage_result = 1
    suspect_info = 'abcd'
    user_name = 'test'

    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    self.MockUTCNow(mocked_now)

    model = _DummyModel()
    model.UpdateTriageResult(1, suspect_info, user_name)
    self.assertEqual(len(model.triage_history), 1)
    self.assertEqual(model.triage_history[0].triage_result, triage_result)
    self.assertEqual(model.triage_history[0].suspect_info, suspect_info)
    self.assertEqual(model.triage_history[0].user_name, user_name)
    self.assertFalse(model.triage_email_obscured)
    self.assertEqual(mocked_now, model.triage_record_last_add)

  def testGetTriageHistory(self):
    suspect_info = {'build_number': 123}
    user_name = 'test'

    model = _DummyModel()
    result = TriageResult()
    result.triage_result = 1
    result.user_name = user_name
    result.suspect_info = suspect_info
    model.triage_history.append(result)

    triage_history = TriagedModel.GetTriageHistory(model)

    # Because TriageResult's triage_time uses auto_now=True, a direct dict
    # comparison will always fail. Instead compare each relevant field
    # individually.
    self.assertEqual(len(triage_history), 1)
    self.assertEqual(triage_history[0].get('user_name'), user_name)
    self.assertEqual(triage_history[0].get('triage_result'), 'Incorrect')
    self.assertEqual(triage_history[0].get('suspect_info'), suspect_info)
