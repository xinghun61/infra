# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from google.appengine.ext import ndb

from analysis.type_enums import CrashClient
from common.model.crash_analysis import CrashAnalysis

_CLUSTERFUZZ_TESTCASE_URL_TEMPLATE = (
    'https://clusterfuzz.com/v2/testcase-detail/%s')


class ClusterfuzzAnalysis(CrashAnalysis):
  """Represents an analysis of a Clusterfuzz crash."""
  # Customized properties for Fracas crash.
  crash_type = ndb.StringProperty()
  crash_address = ndb.StringProperty()
  sanitizer = ndb.StringProperty()
  job_type = ndb.StringProperty()
  testcase_id = ndb.StringProperty()
  security_flag = ndb.BooleanProperty(default=False)

  def Reset(self):
    super(ClusterfuzzAnalysis, self).Reset()
    self.crash_type = None
    self.crash_address = None
    self.sanitizer = None
    self.job_type = None
    self.testcase_id = None
    self.security_flag = False

  def Initialize(self, crash_data):
    """(Re)Initializes a CrashAnalysis ndb.Model from ``ClusterfuzzData``."""
    super(ClusterfuzzAnalysis, self).Initialize(crash_data)
    self.crash_type = crash_data.crash_type
    self.crash_address = crash_data.crash_address
    self.sanitizer = crash_data.sanitizer
    self.job_type = crash_data.job_type
    self.testcase_id = crash_data.testcase_id
    self.security_flag = crash_data.security_flag

  @property
  def client_id(self):  # pragma: no cover
    return CrashClient.CLUSTERFUZZ

  @property
  def crash_url(self):  # pragma: no cover
    return (_CLUSTERFUZZ_TESTCASE_URL_TEMPLATE % self.testcase_id
            if self.testcase_id else '')

  @property
  def customized_data(self):
    return {
        'regression_range': self.regression_range,
        'crash_type': self.crash_type,
        'crash_address': self.crash_address,
        'dependencies': self.dependencies,
        'dependency_rolls': self.dependency_rolls,
        'sanitizer': self.sanitizer,
        'job_type': self.job_type,
        'testcase_id': self.testcase_id,
        'security_flag': self.security_flag,
    }

  def ToJson(self):
    """Converts the ClusterfuzzAnalysis to json that predator can analyze."""
    crash_json = super(ClusterfuzzAnalysis, self).ToJson()
    crash_json['crash_revision'] = self.crashed_version

    customized_data = copy.deepcopy(self.customized_data)
    if self.dependencies:
      customized_data['dependencies'] = [
          {'dep_path': dep.path,
           'repo_url': dep.repo_url,
           'revision': dep.revision}
          for dep in self.dependencies.itervalues()
      ]

    if self.dependency_rolls:
      customized_data['dependency_rolls'] = [
          {'dep_path': dep.path,
           'repo_url': dep.repo_url,
           'old_revision': dep.old_revision,
           'new_revision': dep.new_revision}
          for dep in self.dependency_rolls.itervalues()
      ]

    crash_json['customized_data'] = customized_data
    return crash_json
