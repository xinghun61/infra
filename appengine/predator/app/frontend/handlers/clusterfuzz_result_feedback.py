# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from analysis.type_enums import CrashClient
from frontend.handlers.result_feedback import ResultFeedback
from gae_libs.handlers.base_handler import Permission


class ClusterfuzzResultFeedback(ResultFeedback):
  PERMISSION_LEVEL = Permission.CORP_USER

  @property
  def client(self):
    return CrashClient.CLUSTERFUZZ

  def HandleGet(self):
    key = self.request.get('key')
    analysis = ndb.Key(urlsafe=key).get()
    data = super(ClusterfuzzResultFeedback, self).HandleGet()['data']
    data['testcase_id'] = analysis.testcase_id
    data['job_type'] = analysis.job_type
    data['crash_type'] = analysis.crash_type

    return {
        'template': 'clusterfuzz_result_feedback.html',
        'data': data,
    }
