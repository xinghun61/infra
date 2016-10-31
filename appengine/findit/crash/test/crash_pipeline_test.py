# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
import json
import logging

from google.appengine.api import app_identity
from google.appengine.ext import ndb
from webtest.app import AppError

from common import chrome_dependency_fetcher
from common.pipeline_wrapper import pipeline_handlers
from crash import crash_pipeline
from crash.culprit import Culprit
from crash.findit_for_chromecrash import FinditForFracas
from crash.type_enums import CrashClient
from crash.test.crash_testcase import CrashTestCase
from model import analysis_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis

def DummyCrashData(
    version='1',
    signature='signature',
    platform='win',
    stack_trace=None,
    regression_range=None,
    channel='canary',
    historical_metadata=None,
    crash_identifiers=True,
    process_type='browser'):
  if crash_identifiers is True: # pragma: no cover
    crash_identifiers = {
        'chrome_version': version,
        'signature': signature,
        'channel': channel,
        'platform': platform,
        'process_type': process_type,
    }
  return {
      'crashed_version': version,
      'signature': signature,
      'platform': platform,
      'stack_trace': stack_trace,
      'regression_range': regression_range,
      'crash_identifiers': crash_identifiers,
      'customized_data': {
          'historical_metadata': historical_metadata,
          'channel': channel,
      },
  }


class MockCulprit(object):
  """Construct a fake culprit where ``ToDicts`` returns whatever we please."""

  def __init__(self, mock_result, mock_tags):
    self._result = mock_result
    self._tags = mock_tags

  def ToDicts(self): # pragma: no cover
    return self._result, self._tags


class CrashPipelineTest(CrashTestCase):
  app_module = pipeline_handlers._APP

  def testAnalysisAborted(self):
    crash_identifiers = DummyCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    pipeline = crash_pipeline.CrashAnalysisPipeline(
        CrashClient.FRACAS,
        crash_identifiers)
    pipeline._PutAbortedError()
    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.ERROR, analysis.status)

  def testFindCulpritFails(self):
    crash_identifiers = DummyCrashData()['crash_identifiers']
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    self.mock(FinditForFracas, 'FindCulprit', lambda *_: None)
    pipeline = crash_pipeline.CrashAnalysisPipeline(
        CrashClient.FRACAS,
        crash_identifiers)
    pipeline.run()

    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertFalse(analysis.result['found'])
    self.assertFalse(analysis.found_suspects)
    self.assertFalse(analysis.found_project)
    self.assertFalse(analysis.found_components)

  # TODO: this function is a gross hack. We should figure out what the
  # semantic goal really is here, so we can avoid doing such intricate
  # and fragile mocking.
  def _TestRunningAnalysisForResult(self, analysis_result, analysis_tags):

    # Mock out the part of PublishResultPipeline that would go over the wire.
    pubsub_publish_requests = []
    def Mocked_PublishMessagesToTopic(messages_data, topic):
      pubsub_publish_requests.append((messages_data, topic))
    self.mock(crash_pipeline.pubsub_util, 'PublishMessagesToTopic',
              Mocked_PublishMessagesToTopic)

    MOCK_HOST = 'https://host.com'
    self.mock(app_identity, 'get_default_version_hostname', lambda: MOCK_HOST)

    testcase = self
    MOCK_KEY = 'MOCK_KEY'

    # Mock out the wrapper pipeline, calling the other pipelines directly.
    class _MockPipeline(crash_pipeline.CrashWrapperPipeline):
      def start(self, **kwargs):
        logging.info('Mock running on queue %s', kwargs['queue_name'])
        analysis_pipeline = crash_pipeline.CrashAnalysisPipeline(
            self._client_id, self._crash_identifiers)
        analysis_pipeline.run()
        analysis_pipeline.finalized()

        testcase.mock(ndb.Key, 'urlsafe', lambda _self: MOCK_KEY)
        publish_pipeline = crash_pipeline.PublishResultPipeline(
            self._client_id, self._crash_identifiers)
        publish_pipeline.run()
        publish_pipeline.finalized()

    # Mock out FindCulprit to track the number of times it's called and
    # with which arguments. N.B., the pipeline will reconstruct Findit
    # objects form their client_id, so we can't mock via subclassing,
    # we must mock via ``self.mock``.
    mock_culprit = MockCulprit(analysis_result, analysis_tags)
    analyzed_crashes = []
    def _MockFindCulprit(_self, model):
        analyzed_crashes.append(model)
        return mock_culprit
    self.mock(FinditForFracas, 'FindCulprit', _MockFindCulprit)

    # The real ``ParseStacktrace`` calls ``GetChromeDependency``,
    # which eventually calls ``GitRepository.GetSource`` and hence
    # goes over the wire. Since we mocked out ``FindCulprit`` to no
    # longer call ``ParseStacktrace``, it shouldn't matter what the real
    # ``ParseStacktrace`` does. However, since mocking is fragile and it's
    # hard to triage what actually went wrong if we do end up going over
    # the wire, we mock this out too just to be safe.
    def _MockParseStacktrace(_self, _model):
      raise AssertionError("ParseStacktrace shouldn't ever be called. "
          'That it was indicates some sort of problem with our mocking code.')
    self.mock(FinditForFracas, 'ParseStacktrace', _MockParseStacktrace)

    # More directly address the issue about ``GetChromeDependency`` going
    # over the wire.
    def _MockGetChromeDependency(_self, _revision, _platform):
      raise AssertionError("GetChromeDependency shouldn't ever be called. "
          'That it was indicates some sort of problem with our mocking code.')
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', _MockGetChromeDependency)

    crash_data = DummyCrashData(
        version = '50.2500.0.1',
        stack_trace = 'frame1\nframe2\nframe3')
    # A fake repository, needed by the Findit constructor. We should never
    # go over the wire (e.g., in the call to ScheduleNewAnalysis below),
    # and this helps ensure that. (The current version of the tests
    # don't seem to need the repo at all, so None is a sufficient mock
    # for now.)
    mock_repository = None
    self.assertTrue(
        FinditForFracas(mock_repository, _MockPipeline).ScheduleNewAnalysis(
            crash_data))

    # The catch/re-raise is to clean up the callstack that's reported
    # when things acciddentally go over the wire (and subsequently fail).
    try:
      self.execute_queued_tasks()
    except AppError, e: # pragma: no cover
      raise e

    self.assertEqual(1, len(pubsub_publish_requests))

    processed_analysis_result = copy.deepcopy(analysis_result)
    processed_analysis_result['feedback_url'] = (
        '%s/crash/fracas-result-feedback?key=%s' % (MOCK_HOST, MOCK_KEY))

    for cl in processed_analysis_result.get('suspected_cls', []):
      cl['confidence'] = round(cl['confidence'], 2)
      cl.pop('reason', None)

    expected_messages_data = [json.dumps({
            'crash_identifiers': crash_data['crash_identifiers'],
            'client_id': CrashClient.FRACAS,
            'result': processed_analysis_result,
        }, sort_keys=True)]
    self.assertListEqual(expected_messages_data, pubsub_publish_requests[0][0])
    self.assertEqual(1, len(analyzed_crashes))
    analysis = analyzed_crashes[0]
    self.assertTrue(isinstance(analysis, FracasCrashAnalysis))
    self.assertEqual(crash_data['signature'], analysis.signature)
    self.assertEqual(crash_data['platform'], analysis.platform)
    self.assertEqual(crash_data['stack_trace'], analysis.stack_trace)
    self.assertEqual(crash_data['crashed_version'], analysis.crashed_version)
    self.assertEqual(crash_data['regression_range'], analysis.regression_range)

    analysis = FracasCrashAnalysis.Get(crash_data['crash_identifiers'])
    self.assertEqual(analysis_result, analysis.result)
    return analysis

  def testRunningAnalysis(self):
    analysis_result = {
        'found': True,
        'suspected_cls': [],
        'other_data': 'data',
    }
    analysis_tags = {
        'found_suspects': True,
        'has_regression_range': True,
        'solution': 'core',
        'unsupported_tag': '',
    }

    analysis = self._TestRunningAnalysisForResult(
        analysis_result, analysis_tags)
    self.assertTrue(analysis.has_regression_range)
    self.assertTrue(analysis.found_suspects)
    self.assertEqual('core', analysis.solution)

  def testRunningAnalysisNoSuspectsFound(self):
    analysis_result = {
        'found': False
    }
    analysis_tags = {
        'found_suspects': False,
        'has_regression_range': False,
        'solution': 'core',
        'unsupported_tag': '',
    }

    analysis = self._TestRunningAnalysisForResult(
        analysis_result, analysis_tags)
    self.assertFalse(analysis.has_regression_range)
    self.assertFalse(analysis.found_suspects)
    self.assertEqual('core', analysis.solution)

  def testRunningAnalysisWithSuspectsCls(self):
    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reason': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'other_data': 'data',
    }
    analysis_tags = {
        'found_suspects': True,
        'has_regression_range': True,
        'solution': 'core',
        'unsupported_tag': '',
    }

    analysis = self._TestRunningAnalysisForResult(
        analysis_result, analysis_tags)
    self.assertTrue(analysis.has_regression_range)
    self.assertTrue(analysis.found_suspects)
    self.assertEqual('core', analysis.solution)
