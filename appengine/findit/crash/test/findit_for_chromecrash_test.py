# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import chrome_dependency_fetcher
from common.dependency import DependencyRoll
from crash import chromecrash_parser
from crash import detect_regression_range
from crash import findit
from crash import findit_for_chromecrash
from crash.changelist_classifier import ChangelistClassifier
from crash.chromecrash_parser import ChromeCrashParser
from crash.component_classifier import ComponentClassifier
from crash.crash_report import CrashReport
from crash.culprit import Culprit
from crash.findit_for_chromecrash import FinditForChromeCrash
from crash.findit_for_chromecrash import FinditForFracas
from crash.project_classifier import ProjectClassifier
from crash.suspect import Suspect
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.test.crash_pipeline_test import DummyCrashData
from crash.test.predator_testcase import PredatorTestCase
from crash.type_enums import CrashClient
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs.gitiles.gitiles_repository import GitilesRepository
from model import analysis_status
from model.crash.crash_analysis import CrashAnalysis
from model.crash.fracas_crash_analysis import FracasCrashAnalysis

MOCK_GET_REPOSITORY = lambda _: None # pragma: no cover

class _FinditForChromeCrash(FinditForChromeCrash):  # pylint: disable = W
  # We allow overriding the default ``get_repository`` because one unittest
  # needs to.
  def __init__(self, get_repository=MOCK_GET_REPOSITORY):
    super(_FinditForChromeCrash, self).__init__(get_repository)

  @classmethod
  def _ClientID(cls): # pragma: no cover
    """Avoid throwing a NotImplementedError.

    Since this method is called from ``FinditForChromeCrash.__init__``
    in order to construct the Azalea object, we need to not throw
    exceptions since we want to be able to test the FinditForChromeCrash
    class itself.
    """
    return ''

  @property
  def config(self):
    """Avoid returning None.

    The default ``Findit.config`` will return None if the client
    id is not found in the CrashConfig. This in turn will cause
    ``FinditForChromeCrash.__init__`` to crash, since NoneType doesn't
    have a ``get`` method. In general it's fine for things to crash, since
    noone should make instances of Findit subclasses which don't define
    ``_clientID``; but for this test suite, we want to permit instances
    of FinditForChromeCrash, so that we can test that class directly.
    """
    return {}


def _FinditForFracas():
  """A helper to pass in the standard pipeline class."""
  return FinditForFracas(MOCK_GET_REPOSITORY)


class FinditForChromeCrashTest(PredatorTestCase):

  # TODO(wrengr): what was the purpose of this test? As written it's
  # just testing that mocking works. I'm guessing it was to check that
  # we fail when the analysis is for the wrong client_id; but if so,
  # then we shouldn't need to mock FindCulprit...
  def testFindCulprit(self):
    self.mock(FinditForChromeCrash, 'FindCulprit', lambda self, *_: None)

    # TODO(wrengr): would be less fragile to call
    # FinditForFracas.CreateAnalysis instead; though if I'm right about
    # the original purpose of this test, then this is one of the few
    # places where calling FracasCrashAnalysis directly would actually
    # make sense.
    analysis = FracasCrashAnalysis.Create({'signature': 'sig'})
    # TODO(wrengr): shouldn't FracasCrashAnalysis.Create already have set
    # the client_id?
    analysis.client_id = CrashClient.FRACAS

    findit_client = (
        _FinditForChromeCrash(GitilesRepository.Factory(HttpClientAppengine())))
    self.assertIsNone(findit_client.FindCulprit(analysis))


class FinditForFracasTest(PredatorTestCase):

  def testPlatformRename(self):
    self.assertEqual(_FinditForFracas().RenamePlatform('linux'), 'unix')

  def testCheckPolicyUnsupportedPlatform(self):
    self.assertIsNone(_FinditForFracas().CheckPolicy(DummyCrashData(
        platform = 'unsupported_platform')))

  def testCheckPolicyBlacklistedSignature(self):
    self.assertIsNone(_FinditForFracas().CheckPolicy(DummyCrashData(
        signature = 'Blacklist marker signature')))

  def testCheckPolicyPlatformRename(self):
    new_crash_data = _FinditForFracas().CheckPolicy(DummyCrashData(
        platform = 'linux'))
    self.assertIsNotNone(new_crash_data,
        'FinditForFracas.CheckPolicy unexpectedly returned None')
    self.assertEqual(new_crash_data['platform'], 'unix')

  def testCreateAnalysis(self):
    self.assertIsNotNone(_FinditForFracas().CreateAnalysis(
        {'signature': 'sig'}))

  def testGetAnalysis(self):
    crash_identifiers = {'signature': 'sig'}
    # TODO(wrengr): would be less fragile to call
    # FinditForFracas.CreateAnalysis instead.
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.put()
    self.assertEqual(_FinditForFracas().GetAnalysis(crash_identifiers),
                     analysis)

  def testInitializeAnalysisForFracas(self):
    crash_data = DummyCrashData(platform = 'linux')
    crash_identifiers = crash_data['crash_identifiers']

    findit_client = _FinditForFracas()
    analysis = findit_client.CreateAnalysis(crash_identifiers)
    findit_client._InitializeAnalysis(analysis, crash_data)
    analysis.put()
    analysis = findit_client.GetAnalysis(crash_identifiers)
    self.assertIsNotNone(analysis,
        'FinditForFracas.GetAnalysis unexpectedly returned None')

    self.assertEqual(analysis.crashed_version, crash_data['crashed_version'])
    self.assertEqual(analysis.signature, crash_data['signature'])
    self.assertEqual(analysis.platform, crash_data['platform'])
    self.assertEqual(analysis.stack_trace, crash_data['stack_trace'])
    channel = crash_data['customized_data'].get('channel', None)
    self.assertIsNotNone(channel,
        'channel is unexpectedly not defined in crash_data')
    self.assertEqual(analysis.channel, channel)

  def testNeedsNewAnalysisIsTrueIfNoAnalysisYet(self):
    self.assertTrue(_FinditForFracas()._NeedsNewAnalysis(DummyCrashData()))

  def testNeedsNewAnalysisIsTrueIfLastOneFailed(self):
    findit_client = _FinditForFracas()
    crash_data = DummyCrashData()
    analysis = findit_client.CreateAnalysis(crash_data['crash_identifiers'])
    analysis.status = analysis_status.ERROR
    analysis.put()
    self.assertTrue(findit_client._NeedsNewAnalysis(crash_data))

  def testNeedsNewAnalysisIsFalseIfLastOneIsNotFailed(self):
    findit_client = _FinditForFracas()
    crash_data = DummyCrashData()
    crash_identifiers = crash_data['crash_identifiers']
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED, analysis_status.SKIPPED):
      analysis = findit_client.CreateAnalysis(crash_identifiers)
      analysis.status = status
      analysis.put()
      self.assertFalse(findit_client._NeedsNewAnalysis(crash_data))

  def testFindCulpritForChromeCrashEmptyStacktrace(self):
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', lambda *_: {})
    self.mock(ChromeCrashParser, 'Parse', lambda *_: None)

    analysis = CrashAnalysis()
    analysis.signature = 'signature'
    analysis.platform = 'win'
    analysis.stack_trace = 'frame1\nframe2'
    analysis.crashed_version = '50.0.1234.0'
    analysis.historical_metadata = [
        {'chrome_version': '51.0.1234.0', 'cpm': 0.6}]
    self.assertIsNone(_FinditForChromeCrash().FindCulprit(analysis))

  # TODO(http://crbug.com/659346): why do these mocks give coverage
  # failures? That's almost surely hiding a bug in the tests themselves.
  def testFindCulpritForChromeCrash(self): # pragma: no cover
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependency', lambda *_: {})
    stack = CallStack(0)
    self.mock(ChromeCrashParser, 'Parse',
              lambda *_: Stacktrace([stack], stack))
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
        'GetDependencyRollsDict',
        lambda *_: {
            'src/': DependencyRoll('src/', 'https://repo', '1', '2'),
            'src/add': DependencyRoll('src/add', 'https://repo1', None, '2'),
            'src/delete': DependencyRoll('src/delete', 'https://repo2', '2',
                None)
    })

    dummy_suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    self.mock(ChangelistClassifier, '__call__',
        lambda _self, report:
            [dummy_suspect] if report.regression_range else [])

    self.mock(ComponentClassifier, 'ClassifySuspects', lambda *_: [])
    self.mock(ComponentClassifier, 'ClassifyCallStack', lambda *_: [])
    self.mock(ProjectClassifier, 'ClassifySuspects', lambda *_: '')
    self.mock(ProjectClassifier, 'ClassifyCallStack', lambda *_: '')

    # TODO(wrengr): for both these tests, we should compare Culprit
    # objects directly rather than calling ToDicts and comparing the
    # dictionaries.
    self._testFindCulpritForChromeCrashSucceeds(dummy_suspect)
    self._testFindCulpritForChromeCrashFails()

  def _testFindCulpritForChromeCrashSucceeds(self, dummy_suspect):
    analysis = CrashAnalysis()
    analysis.signature = 'signature'
    analysis.platform = 'win'
    analysis.stack_trace = 'frame1\nframe2'
    analysis.crashed_version = '50.0.1234.0'
    dummy_regression_range = ('50.0.1233.0', '50.0.1234.0')
    analysis.regression_range = dummy_regression_range
    culprit = _FinditForChromeCrash().FindCulprit(analysis)
    self.assertIsNotNone(culprit, 'FindCulprit failed unexpectedly')
    suspects, tag = culprit.ToDicts()

    expected_suspects = {
          'found': True,
          'suspected_cls': [dummy_suspect.ToDict()],
          'regression_range': dummy_regression_range
    }
    expected_tag = {
          'found_suspects': True,
          'found_project': False,
          'found_components': False,
          'has_regression_range': True,
          'solution': 'core_algorithm',
    }

    self.assertDictEqual(expected_suspects, suspects)
    self.assertDictEqual(expected_tag, tag)

  def _testFindCulpritForChromeCrashFails(self):
    analysis = CrashAnalysis()
    analysis.signature = 'signature'
    analysis.platform = 'win'
    analysis.stack_trace = 'frame1\nframe2'
    analysis.crashed_version = '50.0.1234.0'
    # N.B., analysis.regression_range is None
    suspects, tag = _FinditForChromeCrash().FindCulprit(analysis).ToDicts()

    expected_suspects = {'found': False}
    expected_tag = {
          'found_suspects': False,
          'found_project': False,
          'found_components': False,
          'has_regression_range': False,
          'solution': 'core_algorithm',
    }

    self.assertDictEqual(expected_suspects, suspects)
    self.assertDictEqual(expected_tag, tag)

  @mock.patch('google.appengine.ext.ndb.Key.urlsafe')
  @mock.patch('common.appengine_util.GetDefaultVersionHostname')
  def testProcessResultForPublishing(self, mocked_get_default_host,
                                     mocked_urlsafe):
    mocked_host = 'http://host'
    mocked_get_default_host.return_value = mocked_host
    urlsafe_key = 'abcde'
    mocked_urlsafe.return_value = urlsafe_key

    crash_identifiers = {'signature': 'sig'}
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.result = {'other': 'data'}
    findit_object = FinditForFracas(MOCK_GET_REPOSITORY)
    expected_processed_suspect = {
        'client_id': findit_object.client_id,
        'crash_identifiers': {'signature': 'sig'},
        'result': {
            'feedback_url': (
                findit_for_chromecrash._FRACAS_FEEDBACK_URL_TEMPLATE % (
                    mocked_host, urlsafe_key)),
            'other': 'data'
        }
    }

    self.assertDictEqual(findit_object.GetPublishableResult(crash_identifiers,
                                                            analysis),
                         expected_processed_suspect)
