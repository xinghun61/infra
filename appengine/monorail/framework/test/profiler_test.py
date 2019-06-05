# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Test for monorail.framework.profiler."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from framework import profiler


class MockPatchResponse(object):
  def execute(self):
    pass


class MockCloudTraceProjects(object):
  def __init__(self):
    self.patch_response = MockPatchResponse()
    self.project_id = None
    self.body = None

  def patchTraces(self, projectId, body):
    self.project_id = projectId
    self.body = body
    return self.patch_response


class MockCloudTraceApi(object):
  def __init__(self):
    self.mock_projects = MockCloudTraceProjects()

  def projects(self):
    return self.mock_projects


class ProfilerTest(unittest.TestCase):

  def testTopLevelPhase(self):
    prof = profiler.Profiler()
    self.assertEquals(prof.current_phase.name, 'overall profile')
    self.assertEquals(prof.current_phase.parent, None)
    self.assertEquals(prof.current_phase, prof.top_phase)
    self.assertEquals(prof.next_color, 0)

  def testSinglePhase(self):
    prof = profiler.Profiler()
    self.assertEquals(prof.current_phase.name, 'overall profile')
    with prof.Phase('test'):
      self.assertEquals(prof.current_phase.name, 'test')
      self.assertEquals(prof.current_phase.parent.name, 'overall profile')
    self.assertEquals(prof.current_phase.name, 'overall profile')
    self.assertEquals(prof.next_color, 1)

  def testSinglePhase_SuperLongName(self):
    prof = profiler.Profiler()
    self.assertEquals(prof.current_phase.name, 'overall profile')
    long_name = 'x' * 1000
    with prof.Phase(long_name):
      self.assertEquals(
          'x' * profiler.MAX_PHASE_NAME_LENGTH, prof.current_phase.name)

  def testSubphaseExecption(self):
    prof = profiler.Profiler()
    try:
      with prof.Phase('foo'):
        with prof.Phase('bar'):
          pass
        with prof.Phase('baz'):
          raise Exception('whoops')
    except Exception as e:
      self.assertEquals(e.message, 'whoops')
    finally:
      self.assertEquals(prof.current_phase.name, 'overall profile')
      self.assertEquals(
          prof.top_phase.subphases[0].subphases[1].name, 'baz')

  def testSpanJson(self):
    mock_trace_api = MockCloudTraceApi()
    mock_trace_context = '1234/5678;xxxxx'

    prof = profiler.Profiler(mock_trace_context, mock_trace_api)
    with prof.Phase('foo'):
      with prof.Phase('bar'):
        pass
      with prof.Phase('baz'):
        pass

    # Shouldn't this be automatic?
    prof.current_phase.End()

    self.assertEquals(prof.current_phase.name, 'overall profile')
    self.assertEquals(
        prof.top_phase.subphases[0].subphases[1].name, 'baz')
    span_json = prof.top_phase.SpanJson()
    self.assertEquals(len(span_json), 4)

    for span in span_json:
      self.assertTrue(span['endTime'] > span['startTime'])

    # pylint: disable=unbalanced-tuple-unpacking
    span1, span2, span3, span4 = span_json

    self.assertEquals(span1['name'], 'overall profile')
    self.assertEquals(span2['name'], 'foo')
    self.assertEquals(span3['name'], 'bar')
    self.assertEquals(span4['name'], 'baz')

    self.assertTrue(span1['startTime'] < span2['startTime'])
    self.assertTrue(span1['startTime'] < span3['startTime'])
    self.assertTrue(span1['startTime'] < span4['startTime'])

    self.assertTrue(span1['endTime'] > span2['endTime'])
    self.assertTrue(span1['endTime'] > span3['endTime'])
    self.assertTrue(span1['endTime'] > span4['endTime'])


  def testReportCloudTrace(self):
    mock_trace_api = MockCloudTraceApi()
    mock_trace_context = '1234/5678;xxxxx'

    prof = profiler.Profiler(mock_trace_context, mock_trace_api)
    with prof.Phase('foo'):
      with prof.Phase('bar'):
        pass
      with prof.Phase('baz'):
        pass

    # Shouldn't this be automatic?
    prof.current_phase.End()

    self.assertEquals(prof.current_phase.name, 'overall profile')
    self.assertEquals(
        prof.top_phase.subphases[0].subphases[1].name, 'baz')

    prof.ReportTrace()
    self.assertEquals(mock_trace_api.mock_projects.project_id, 'testing-app')
