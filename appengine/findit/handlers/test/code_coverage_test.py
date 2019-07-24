# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import webapp2

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from handlers import code_coverage
from libs.gitiles.gitiles_repository import GitilesRepository
from model.code_coverage import DependencyRepository
from model.code_coverage import FileCoverageData
from model.code_coverage import PostsubmitReport
from model.code_coverage import PresubmitCoverageData
from model.code_coverage import SummaryCoverageData
from waterfall.test.wf_testcase import WaterfallTestCase


def _CreateSampleCoverageSummaryMetric():
  """Returns a sample coverage summary metric for testing purpose.

  Note: only use this method if the exact values don't matter.
  """
  return [{
      'covered': 1,
      'total': 2,
      'name': 'region'
  }, {
      'covered': 1,
      'total': 2,
      'name': 'function'
  }, {
      'covered': 1,
      'total': 2,
      'name': 'line'
  }]


def _CreateSampleManifest():
  """Returns a sample manifest for testing purpose.

  Note: only use this method if the exact values don't matter.
  """
  return [
      DependencyRepository(
          path='//',
          server_host='chromium.googlesource.com',
          project='chromium/src.git',
          revision='ccccc')
  ]


def _CreateSamplePostsubmitReport(manifest=None):
  """Returns a sample PostsubmitReport for testing purpose.

  Note: only use this method if the exact values don't matter.
  """
  manifest = manifest or _CreateSampleManifest()
  return PostsubmitReport.Create(
      server_host='chromium.googlesource.com',
      project='chromium/src',
      ref='refs/heads/master',
      revision='aaaaa',
      bucket='coverage',
      builder='linux-code-coverage',
      commit_position=100,
      commit_timestamp=datetime.datetime(2018, 1, 1),
      manifest=manifest,
      summary_metrics=_CreateSampleCoverageSummaryMetric(),
      build_id=123456789,
      visible=True)


def _CreateSampleDirectoryCoverageData():
  """Returns a sample directory SummaryCoverageData for testing purpose.

  Note: only use this method if the exact values don't matter.
  """
  return SummaryCoverageData.Create(
      server_host='chromium.googlesource.com',
      project='chromium/src',
      ref='refs/heads/master',
      revision='aaaaa',
      data_type='dirs',
      path='//dir/',
      bucket='coverage',
      builder='linux-code-coverage',
      data={
          'dirs': [],
          'path':
              '//dir/',
          'summaries':
              _CreateSampleCoverageSummaryMetric(),
          'files': [{
              'path': '//dir/test.cc',
              'name': 'test.cc',
              'summaries': _CreateSampleCoverageSummaryMetric()
          }]
      })


def _CreateSampleComponentCoverageData():
  """Returns a sample component SummaryCoverageData for testing purpose.

  Note: only use this method if the exact values don't matter.
  """
  return SummaryCoverageData.Create(
      server_host='chromium.googlesource.com',
      project='chromium/src',
      ref='refs/heads/master',
      revision='aaaaa',
      data_type='components',
      path='Component>Test',
      bucket='coverage',
      builder='linux-code-coverage',
      data={
          'dirs': [{
              'path': '//dir/',
              'name': 'dir/',
              'summaries': _CreateSampleCoverageSummaryMetric()
          }],
          'path':
              'Component>Test',
          'summaries':
              _CreateSampleCoverageSummaryMetric()
      })


def _CreateSampleRootComponentCoverageData():
  """Returns a sample component SummaryCoverageData for >> for testing purpose.

  Note: only use this method if the exact values don't matter.
  """
  return SummaryCoverageData.Create(
      server_host='chromium.googlesource.com',
      project='chromium/src',
      ref='refs/heads/master',
      revision='aaaaa',
      data_type='components',
      path='>>',
      bucket='coverage',
      builder='linux-code-coverage',
      data={
          'dirs': [{
              'path': 'Component>Test',
              'name': 'Component>Test',
              'summaries': _CreateSampleCoverageSummaryMetric()
          }],
          'path':
              '>>'
      })


def _CreateSampleFileCoverageData():
  """Returns a sample FileCoverageData for testing purpose.

  Note: only use this method if the exact values don't matter.
  """
  return FileCoverageData.Create(
      server_host='chromium.googlesource.com',
      project='chromium/src',
      ref='refs/heads/master',
      revision='aaaaa',
      path='//dir/test.cc',
      bucket='coverage',
      builder='linux-code-coverage',
      data={
          'path': '//dir/test.cc',
          'revision': 'bbbbb',
          'lines': [{
              'count': 100,
              'last': 2,
              'first': 1
          }],
          'total_lines': 2,
          'timestamp': '140000',
          'uncovered_blocks': [{
              'line': 1,
              'ranges': [{
                  'first': 1,
                  'last': 2
              }]
          }]
      })


class FetchSourceFileTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/coverage/task/fetch-source-file', code_coverage.FetchSourceFile),
      ('/coverage/task/process-data/.*', code_coverage.ProcessCodeCoverageData),
  ],
                                       debug=True)

  def testPermissionInProcessCodeCoverageData(self):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    response = self.test_app.post(
        '/coverage/task/process-data/123?format=json', status=401)
    self.assertEqual(('Either not log in yet or no permission. '
                      'Please log in with your @google.com account.'),
                     response.json_body.get('error_message'))

  @mock.patch.object(code_coverage, '_WriteFileContentToGs')
  @mock.patch.object(GitilesRepository, 'GetSource', return_value='test')
  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testFetchSourceFile(self, mocked_is_request_from_appself,
                          mocked_gitiles_get_source, mocked_write_to_gs):
    path = '//v8/src/dir/file.cc'
    revision = 'bbbbb'

    manifest = [
        DependencyRepository(
            path='//v8/',
            server_host='chromium.googlesource.com',
            project='v8/v8.git',
            revision='zzzzz')
    ]
    report = _CreateSamplePostsubmitReport(manifest=manifest)
    report.put()

    request_url = '/coverage/task/fetch-source-file'
    params = {
        'report_key': report.key.urlsafe(),
        'path': path,
        'revision': revision
    }
    response = self.test_app.post(request_url, params=params)
    self.assertEqual(200, response.status_int)
    mocked_is_request_from_appself.assert_called()

    # Gitiles should fetch the revision of last_updated_revision instead of
    # root_repo_revision and the path should be relative to //v8/.
    mocked_gitiles_get_source.assert_called_with('src/dir/file.cc', 'bbbbb')
    mocked_write_to_gs.assert_called_with(
        ('/source-files-for-coverage/chromium.googlesource.com/v8/v8.git/'
         'src/dir/file.cc/bbbbb'), 'test')


class ProcessCodeCoverageDataTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/coverage/task/process-data/.*', code_coverage.ProcessCodeCoverageData),
  ],
                                       debug=True)

  @mock.patch.object(code_coverage, '_GetValidatedData')
  @mock.patch.object(code_coverage, 'GetV2Build')
  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testProcessCLPatchData(self, mocked_is_request_from_appself,
                             mocked_get_build, mocked_get_validated_data):
    # Mock buildbucket v2 API.
    build = mock.Mock()
    build.builder.project = 'chromium'
    build.builder.bucket = 'try'
    build.builder.builder = 'linux-rel'
    build.output.properties.items.return_value = [
        ('coverage_gs_bucket', 'code-coverage-data'),
        ('coverage_metadata_gs_path',
         ('presubmit/chromium-review.googlesource.com/138000/4/try/'
          'linux-rel/123456789/metadata'))
    ]
    build.input.gerrit_changes = [
        mock.Mock(
            host='chromium-review.googlesource.com', change=138000, patchset=4)
    ]
    mocked_get_build.return_value = build

    # Mock get validated data from cloud storage.
    coverage_data = {
        'dirs':
            None,
        'files': [{
            'path':
                '//dir/test.cc',
            'lines': [{
                'count': 100,
                'first': 1,
                'last': 1,
            }, {
                'count': 0,
                'first': 2,
                'last': 2,
            }],
            'total_lines':
                2
        }],
        'summaries':
            None,
        'components':
            None,
    }
    mocked_get_validated_data.return_value = coverage_data

    request_url = '/coverage/task/process-data/build/123456789'
    response = self.test_app.post(request_url)
    self.assertEqual(200, response.status_int)
    mocked_is_request_from_appself.assert_called()

    mocked_get_validated_data.assert_called_with(
        '/code-coverage-data/presubmit/chromium-review.googlesource.com/138000/'
        '4/try/linux-rel/123456789/metadata/all.json.gz')

    expected_entity = PresubmitCoverageData.Create(
        server_host='chromium-review.googlesource.com',
        change=138000,
        patchset=4,
        build_id=123456789,
        data=coverage_data['files'])
    fetched_entities = PresubmitCoverageData.query().fetch()

    self.assertEqual(1, len(fetched_entities))
    self.assertEqual(expected_entity, fetched_entities[0])
    data = fetched_entities[0].data
    self.assertEqual('//dir/test.cc', data[0]['path'])
    self.assertEqual(1, data[0]['covered_lines'])
    self.assertEqual(2, data[0]['total_lines'])
    self.assertEqual(50, data[0]['absolute_coverage_percentage'])

  @mock.patch.object(code_coverage.ProcessCodeCoverageData,
                     '_FetchAndSaveFileIfNecessary')
  @mock.patch.object(code_coverage, '_RetrieveManifest')
  @mock.patch.object(code_coverage.CachedGitilesRepository, 'GetChangeLog')
  @mock.patch.object(code_coverage, '_GetValidatedData')
  @mock.patch.object(code_coverage, 'GetV2Build')
  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testProcessFullRepoData(self, mocked_is_request_from_appself,
                              mocked_get_build, mocked_get_validated_data,
                              mocked_get_change_log, mocked_retrieve_manifest,
                              mocked_fetch_file):
    # Mock buildbucket v2 API.
    build = mock.Mock()
    build.builder.project = 'chrome'
    build.builder.bucket = 'coverage'
    build.builder.builder = 'linux-code-coverage'
    build.output.properties.items.return_value = [
        ('coverage_gs_bucket', 'code-coverage-data'),
        ('coverage_metadata_gs_path',
         ('postsubmit/chromium.googlesource.com/chromium/src/'
          'aaaaa/coverage/linux-code-coverage/123456789/metadata'))
    ]
    build.input.gitiles_commit = mock.Mock(
        host='chromium.googlesource.com',
        project='chromium/src',
        ref='refs/heads/master',
        id='aaaaa')
    mocked_get_build.return_value = build

    # Mock Gitiles API to get change log.
    change_log = mock.Mock()
    change_log.commit_position = 100
    change_log.committer.time = datetime.datetime(2018, 1, 1)
    mocked_get_change_log.return_value = change_log

    # Mock retrieve manifest.
    manifest = _CreateSampleManifest()
    mocked_retrieve_manifest.return_value = manifest

    # Mock get validated data from cloud storage for both all.json and file
    # shard json.
    all_coverage_data = {
        'dirs': [{
            'path':
                '//dir/',
            'dirs': [],
            'files': [{
                'path': '//dir/test.cc',
                'name': 'test.cc',
                'summaries': _CreateSampleCoverageSummaryMetric()
            }],
            'summaries':
                _CreateSampleCoverageSummaryMetric()
        }],
        'file_shards': ['file_coverage/files1.json.gz'],
        'summaries':
            _CreateSampleCoverageSummaryMetric(),
        'components': [{
            'path':
                'Component>Test',
            'dirs': [{
                'path': '//dir/',
                'name': 'dir/',
                'summaries': _CreateSampleCoverageSummaryMetric()
            }],
            'summaries':
                _CreateSampleCoverageSummaryMetric()
        }],
    }

    file_shard_coverage_data = {
        'files': [{
            'path':
                '//dir/test.cc',
            'revision':
                'bbbbb',
            'lines': [{
                'count': 100,
                'last': 2,
                'first': 1
            }],
            'total_lines':
                2,
            'timestamp':
                '140000',
            'uncovered_blocks': [{
                'line': 1,
                'ranges': [{
                    'first': 1,
                    'last': 2
                }]
            }]
        }]
    }

    mocked_get_validated_data.side_effect = [
        all_coverage_data, file_shard_coverage_data
    ]

    request_url = '/coverage/task/process-data/build/123456789'
    response = self.test_app.post(request_url)
    self.assertEqual(200, response.status_int)
    mocked_is_request_from_appself.assert_called()

    fetched_reports = PostsubmitReport.query().fetch()
    self.assertEqual(1, len(fetched_reports))
    self.assertEqual(_CreateSamplePostsubmitReport(), fetched_reports[0])
    mocked_fetch_file.assert_called_with(_CreateSamplePostsubmitReport(),
                                         '//dir/test.cc', 'bbbbb')

    fetched_file_coverage_data = FileCoverageData.query().fetch()
    self.assertEqual(1, len(fetched_file_coverage_data))
    self.assertEqual(_CreateSampleFileCoverageData(),
                     fetched_file_coverage_data[0])

    fetched_summary_coverage_data = SummaryCoverageData.query().fetch()
    self.assertListEqual([
        _CreateSampleRootComponentCoverageData(),
        _CreateSampleComponentCoverageData(),
        _CreateSampleDirectoryCoverageData()
    ], fetched_summary_coverage_data)


class ServeCodeCoverageDataTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/coverage/api/coverage-data', code_coverage.ServeCodeCoverageData),
      ('.*/coverage', code_coverage.ServeCodeCoverageData),
      ('.*/coverage/component', code_coverage.ServeCodeCoverageData),
      ('.*/coverage/dir', code_coverage.ServeCodeCoverageData),
      ('.*/coverage/file', code_coverage.ServeCodeCoverageData),
  ],
                                       debug=True)

  def testServeCLPatchCoverageData(self):
    self.UpdateUnitTestConfigSettings('code_coverage_settings',
                                      {'serve_presubmit_coverage_data': True})

    host = 'chromium-review.googlesource.com'
    project = 'chromium/src'
    change = 138000
    patchset = 4
    build_id = 123456789
    data = [{
        'path': '//dir/test.cc',
        'lines': [{
            'count': 100,
            'first': 1,
            'last': 2,
        }],
        'total_lines': 2
    }]
    PresubmitCoverageData.Create(
        server_host=host,
        change=change,
        patchset=patchset,
        build_id=build_id,
        data=data).put()

    request_url = ('/coverage/api/coverage-data?host=%s&project=%s&change=%s'
                   '&patchset=%s&concise=1') % (host, project, change, patchset)
    response = self.test_app.get(request_url)

    expected_response_body = json.dumps({
        'project': 'chromium/src',
        'host': 'chromium-review.googlesource.com',
        'data': {
            'files': [{
                'path': 'dir/test.cc',
                'lines': [{
                    'count': 100,
                    'line': 1
                }, {
                    'count': 100,
                    'line': 2
                }]
            }]
        },
        'patchset': '4',
        'change': '138000'
    })
    self.assertEqual(expected_response_body, response.body)

  def testServeFullRepoProjectView(self):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    host = 'chromium.googlesource.com'
    project = 'chromium/src'
    platform = 'linux'

    report = _CreateSamplePostsubmitReport()
    report.put()

    request_url = (
        '/p/chromium/coverage?host=%s&project=%s&platform=%s&list_reports=true'
    ) % (host, project, platform)
    response = self.test_app.get(request_url)
    self.assertEqual(200, response.status_int)

  def testServeFullRepoDirectoryView(self):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    host = 'chromium.googlesource.com'
    project = 'chromium/src'
    ref = 'refs/heads/master'
    revision = 'aaaaa'
    path = '//dir/'
    platform = 'linux'

    report = _CreateSamplePostsubmitReport()
    report.put()

    dir_coverage_data = _CreateSampleDirectoryCoverageData()
    dir_coverage_data.put()

    request_url = (
        '/p/chromium/coverage/dir?host=%s&project=%s&ref=%s&revision=%s'
        '&path=%s&platform=%s') % (host, project, ref, revision, path, platform)
    response = self.test_app.get(request_url)
    self.assertEqual(200, response.status_int)

  def testServeFullRepoComponentView(self):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    host = 'chromium.googlesource.com'
    project = 'chromium/src'
    ref = 'refs/heads/master'
    revision = 'aaaaa'
    path = 'Component>Test'
    platform = 'linux'

    report = _CreateSamplePostsubmitReport()
    report.put()

    component_coverage_data = _CreateSampleComponentCoverageData()
    component_coverage_data.put()

    request_url = ('/p/chromium/coverage/component?host=%s&project=%s&ref=%s'
                   '&revision=%s&path=%s&platform=%s') % (
                       host, project, ref, revision, path, platform)
    response = self.test_app.get(request_url)
    self.assertEqual(200, response.status_int)

  @mock.patch.object(code_coverage, '_GetFileContentFromGs')
  def testServeFullRepoFileView(self, mock_get_file_from_gs):
    self.mock_current_user(user_email='test@google.com', is_admin=False)
    mock_get_file_from_gs.return_value = 'line one/nline two'

    host = 'chromium.googlesource.com'
    project = 'chromium/src'
    ref = 'refs/heads/master'
    revision = 'aaaaa'
    path = '//dir/test.cc'
    platform = 'linux'

    report = _CreateSamplePostsubmitReport()
    report.put()

    file_coverage_data = _CreateSampleFileCoverageData()
    file_coverage_data.put()

    request_url = ('/p/chromium/coverage/file?host=%s&project=%s&ref=%s'
                   '&revision=%s&path=%s&platform=%s') % (
                       host, project, ref, revision, path, platform)
    response = self.test_app.get(request_url)
    self.assertEqual(200, response.status_int)
    mock_get_file_from_gs.assert_called_with(
        '/source-files-for-coverage/chromium.googlesource.com/chromium/'
        'src.git/dir/test.cc/bbbbb')

  @mock.patch.object(code_coverage, '_GetFileContentFromGs')
  def testServeFullRepoFileViewWithNonAsciiChars(self, mock_get_file_from_gs):
    self.mock_current_user(user_email='test@google.com', is_admin=False)
    mock_get_file_from_gs.return_value = 'line one\n═══════════╪'
    report = _CreateSamplePostsubmitReport()
    report.put()

    file_coverage_data = _CreateSampleFileCoverageData()
    file_coverage_data.put()

    request_url = ('/p/chromium/coverage/file?host=%s&project=%s&ref=%s'
                   '&revision=%s&path=%s&platform=%s') % (
                       'chromium.googlesource.com', 'chromium/src',
                       'refs/heads/master', 'aaaaa', '//dir/test.cc', 'linux')
    response = self.test_app.get(request_url)
    self.assertEqual(200, response.status_int)


class SplitLineIntoRegionsTest(WaterfallTestCase):

  def testRejoinSplitRegions(self):
    line = 'the quick brown fox jumped over the lazy dog'
    blocks = [{
        'first': 4,
        'last': 10,
    }, {
        'first': 20,
        'last': 23,
    }, {
        'first': 42,
        'last': 43,
    }]
    regions = code_coverage._SplitLineIntoRegions(line, blocks)
    reconstructed_line = ''.join(region['text'] for region in regions)
    self.assertEqual(line, reconstructed_line)

  def testRegionsCorrectlySplit(self):
    line = 'onetwothreefourfivesixseven'
    blocks = [{
        'first': 4,
        'last': 6,
    }, {
        'first': 12,
        'last': 15,
    }, {
        'first': 20,
        'last': 22,
    }]
    regions = code_coverage._SplitLineIntoRegions(line, blocks)

    self.assertEqual('one', regions[0]['text'])
    self.assertEqual('two', regions[1]['text'])
    self.assertEqual('three', regions[2]['text'])
    self.assertEqual('four', regions[3]['text'])
    self.assertEqual('five', regions[4]['text'])
    self.assertEqual('six', regions[5]['text'])
    self.assertEqual('seven', regions[6]['text'])

    # Regions should alternate between covered and uncovered.
    self.assertTrue(regions[0]['is_covered'])
    self.assertTrue(regions[2]['is_covered'])
    self.assertTrue(regions[4]['is_covered'])
    self.assertTrue(regions[6]['is_covered'])
    self.assertFalse(regions[1]['is_covered'])
    self.assertFalse(regions[3]['is_covered'])
    self.assertFalse(regions[5]['is_covered'])

  def testPrefixUncovered(self):
    line = 'NOCOVcov'
    blocks = [{'first': 1, 'last': 5}]
    regions = code_coverage._SplitLineIntoRegions(line, blocks)
    self.assertEqual('NOCOV', regions[0]['text'])
    self.assertEqual('cov', regions[1]['text'])
    self.assertFalse(regions[0]['is_covered'])
    self.assertTrue(regions[1]['is_covered'])

  def testSuffixUncovered(self):
    line = 'covNOCOV'
    blocks = [{'first': 4, 'last': 8}]
    regions = code_coverage._SplitLineIntoRegions(line, blocks)
    self.assertEqual('cov', regions[0]['text'])
    self.assertEqual('NOCOV', regions[1]['text'])
    self.assertTrue(regions[0]['is_covered'])
    self.assertFalse(regions[1]['is_covered'])
