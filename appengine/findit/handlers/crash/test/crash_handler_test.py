# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import copy
import json
import logging

from google.appengine.api import app_identity
from google.appengine.ext import ndb
import webapp2
from webtest.app import AppError

from common import chrome_dependency_fetcher
from crash import crash_pipeline
from crash.findit import Findit
from crash.findit_for_chromecrash import FinditForFracas
from crash.test.predator_testcase import PredatorTestCase
from crash.type_enums import CrashClient
from handlers.crash import crash_handler
from libs.gitiles import gitiles_repository
from model import analysis_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


MOCK_GET_REPOSITORY = lambda _: None # pragma: no cover


class MockCulprit(object):
  """Construct a fake culprit where ``ToDicts`` returns whatever we please."""

  def __init__(self, mock_result, mock_tags):
    self._result = mock_result
    self._tags = mock_tags

  def ToDicts(self): # pragma: no cover
    return self._result, self._tags


class CrashHandlerTest(PredatorTestCase):
  app_module = webapp2.WSGIApplication([
      ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
  ], debug=True)

  def testScheduleNewAnalysisWithFailingPolicy(self):
    class _MockFindit(Findit): # pylint: disable=W0223
      def __init__(self):
        super(_MockFindit, self).__init__(MOCK_GET_REPOSITORY)

      def CheckPolicy(self, crash_data):
        """This is the same as inherited, but just to be explicit."""
        return None

      def _NeedsNewAnalysis(self, _crash_data):
        raise AssertionError('testScheduleNewAnalysisWithFailingPolicy: '
            "called _MockFindit._NeedsNewAnalysis, when it shouldn't.")

    self.mock(crash_pipeline, 'FinditForClientID', lambda *_: _MockFindit())
    self.assertFalse(crash_handler.ScheduleNewAnalysis(self.GetDummyCrashData(
        client_id = 'MOCK_CLIENT')))

  def testScheduleNewAnalysisWithPlatformRename(self):
    original_crash_data = self.GetDummyCrashData(
        client_id = 'MOCK_CLIENT',
        version = None,
        platform = 'unix',
        crash_identifiers = {})
    renamed_crash_data = copy.deepcopy(original_crash_data)
    renamed_crash_data['platform'] = 'linux'

    testcase = self
    class _MockFindit(Findit): # pylint: disable=W0223
      def __init__(self):
        super(_MockFindit, self).__init__(MOCK_GET_REPOSITORY)

      @property
      def config(self):
        """Make PlatformRename work as expected."""
        return {'platform_rename': {'unix': 'linux'}}

      def CheckPolicy(self, crash_data):
        """Call PlatformRename, and return successfully.

        N.B., if we did not override this method, then our overridden
        ``_NeedsNewAnalysis`` would never be called either."""
        # TODO(wrengr): should we clone ``crash_data`` rather than mutating it?
        crash_data['platform'] = self.RenamePlatform(crash_data['platform'])
        return crash_data

      def _NeedsNewAnalysis(self, new_crash_data):
        logging.debug('Called _MockFindit._NeedsNewAnalysis, as desired')
        testcase.assertDictEqual(new_crash_data, renamed_crash_data)
        return False

    self.mock(crash_pipeline, 'FinditForClientID',
        lambda _client_id, repository: _MockFindit())
    self.assertFalse(crash_handler.ScheduleNewAnalysis(original_crash_data))

  def testScheduleNewAnalysisSkipsUnsupportedChannel(self):
    self.assertFalse(crash_handler.ScheduleNewAnalysis(self.GetDummyCrashData(
        client_id = CrashClient.FRACAS,
        version = None,
        signature = None,
        crash_identifiers = {},
        channel = 'unsupported_channel')))

  def testScheduleNewAnalysisSkipsUnsupportedPlatform(self):
    self.assertFalse(crash_handler.ScheduleNewAnalysis(self.GetDummyCrashData(
        client_id = CrashClient.FRACAS,
        version = None,
        signature = None,
        platform = 'unsupported_platform',
        crash_identifiers = {})))

  def testScheduleNewAnalysisSkipsBlackListSignature(self):
    self.assertFalse(crash_handler.ScheduleNewAnalysis(self.GetDummyCrashData(
        client_id = CrashClient.FRACAS,
        version = None,
        signature = 'Blacklist marker signature',
        crash_identifiers = {})))

  def testScheduleNewAnalysisSkipsIfAlreadyCompleted(self):
    findit_client = FinditForFracas(MOCK_GET_REPOSITORY)
    crash_data = self.GetDummyCrashData(client_id = findit_client.client_id)
    crash_identifiers = crash_data['crash_identifiers']
    analysis = findit_client.CreateAnalysis(crash_identifiers)
    analysis.status = analysis_status.COMPLETED
    analysis.put()
    self.assertFalse(crash_handler.ScheduleNewAnalysis(crash_data))

  def testAnalysisScheduled(self):
    # We need to mock out the method on Findit itself (rather than using a
    # subclass), since this method only gets called on objects we
    # ourselves don't construct.
    requested_crashes = []
    def _MockScheduleNewAnalysis(crash_data):
      requested_crashes.append(crash_data)
    self.mock(crash_handler, 'ScheduleNewAnalysis', _MockScheduleNewAnalysis)

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    channel = 'supported_channel'
    platform = 'supported_platform'
    signature = 'signature/here'
    chrome_version = '50.2500.0.0'
    crash_data = {
        'client_id': 'fracas',
        'platform': platform,
        'signature': signature,
        'stack_trace': 'frame1\nframe2\nframe3',
        'chrome_version': chrome_version,
        'crash_identifiers': {
            'chrome_version': chrome_version,
            'signature': signature,
            'channel': channel,
            'platform': platform,
            'process_type': 'renderer',
        },
        'customized_data': {
            'channel': channel,
            'historical_metadata':
                [{'chrome_version': chrome_version, 'cpm': 0.6}],
        },
    }

    request_json_data = {
        'message': {
            'data': base64.b64encode(json.dumps(crash_data)),
            'message_id': 'id',
        },
        'subscription': 'subscription',
    }

    self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                            request_json_data)

    self.assertEqual(1, len(requested_crashes))
    self.assertEqual(crash_data, requested_crashes[0])

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

    MOCK_HOST = 'host.com'
    self.mock(app_identity, 'get_default_version_hostname', lambda: MOCK_HOST)

    testcase = self
    MOCK_KEY = 'MOCK_KEY'

    # Mock out the wrapper pipeline, so call the other pipelines directly
    # instead of doing the yielding loop and spawning off processes.
    def mock_start_pipeline(self, **kwargs):
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
    self.mock(crash_pipeline.CrashWrapperPipeline, 'start', mock_start_pipeline)

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

    crash_data = self.GetDummyCrashData(
        client_id = CrashClient.FRACAS,
        version = '50.2500.0.1',
        stack_trace = 'frame1\nframe2\nframe3')
    self.assertTrue(crash_handler.ScheduleNewAnalysis(crash_data))

    # The catch/re-raise is to clean up the callstack that's reported
    # when things acciddentally go over the wire (and subsequently fail).
    try:
      self.execute_queued_tasks()
    except AppError, e: # pragma: no cover
      raise e

    self.assertEqual(1, len(pubsub_publish_requests))

    processed_analysis_result = copy.deepcopy(analysis_result)
    processed_analysis_result['feedback_url'] = (
        'https://%s/crash/fracas-result-feedback?key=%s' % (MOCK_HOST,
                                                            MOCK_KEY))

    for cl in processed_analysis_result.get('suspected_cls', []):
      cl['confidence'] = round(cl['confidence'], 2)
      cl.pop('reasons', None)

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
    self.assertEqual(crash_data['chrome_version'], analysis.crashed_version)
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
             'reasons': ['reason1', 'reason2'],
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
