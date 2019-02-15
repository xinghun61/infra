# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict


class _ActualTestResultByStatusGroup(object):
  """Counts of classified results by status group for a single test."""

  def __init__(self, passes=None, failures=None, skips=None, unknowns=None,
               notruns=None):
    self.passes = passes or defaultdict(int)
    self.failures = failures or defaultdict(int)
    self.skips = skips or defaultdict(int)
    self.unknowns = unknowns or defaultdict(int)
    self.notruns = notruns or defaultdict(int)

  @classmethod
  def FromDict(cls, info):
    return cls(info['passes'], info['failures'], info['skips'],
               info['unknowns'], info['notruns'])

  def ToDict(self):
    return {
        'passes': self.passes,
        'failures': self.failures,
        'skips': self.skips,
        'unknowns': self.unknowns,
        'notruns': self.notruns
    }


class _ClassifiedTestResult(object):
  """Represents classified result for a single test.

  It has different counts of results:
  * Counts of classified results by status group;
  * Counts of classified results by whether the result is expected.
  """

  def __init__(self,
               total_run=0,
               num_expected_results=0,
               num_unexpected_results=0,
               results=None):
    self.total_run = total_run
    self.num_expected_results = num_expected_results
    self.num_unexpected_results = num_unexpected_results
    self.results = results or _ActualTestResultByStatusGroup()

  @classmethod
  def FromDict(cls, info):
    return cls(info['total_run'], info['num_expected_results'],
               info['num_unexpected_results'],
               _ActualTestResultByStatusGroup.FromDict(info['results']))

  def ToDict(self):
    return {
        'total_run': self.total_run,
        'num_expected_results': self.num_expected_results,
        'num_unexpected_results': self.num_unexpected_results,
        'results': self.results.ToDict()
    }


class ClassifiedTestResults(defaultdict):
  """A defaultdict of _ClassifiedTestResult for all tests."""

  def __init__(self, *args, **kwargs):
    super(ClassifiedTestResults, self).__init__(*args, **kwargs)
    self.default_factory = _ClassifiedTestResult

  @classmethod
  def FromDict(cls, info):
    instance = cls()
    for key, value in info.iteritems():
      instance[key] = _ClassifiedTestResult.FromDict(value)
    return instance

  def ToDict(self):
    data_dict = {}
    for key, value in self.iteritems():
      data_dict[key] = value.ToDict()
    return data_dict
