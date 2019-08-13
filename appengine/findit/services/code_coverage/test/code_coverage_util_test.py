# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import textwrap

from google.appengine.ext import ndb

from model.code_coverage import CoveragePercentage
from services.code_coverage import code_coverage_util
from waterfall.test.wf_testcase import WaterfallTestCase


def _CreateNDBFuture(result):
  future = ndb.Future()
  future.set_result(result)
  return future


class CodeCoverageUtilTest(WaterfallTestCase):

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testGetEquivalentPatchsets(self, mock_http_client):
    mock_http_client.return_value = (
        200,
        json.dumps({
            'status': 'NEW',
            'revisions': {
                'aaaaaaaaaaa': {
                    '_number': 8,
                    'kind': 'TRIVIAL_REBASE',
                },
                'bbbbbbbbbbb': {
                    '_number': 7,
                    'kind': 'TRIVIAL_REBASE',
                },
                'ccccccccccc': {
                    '_number': 6,
                    'kind': 'MERGE_FIRST_PARENT_UPDATE',
                },
                'ddddddddddd': {
                    '_number': 5,
                    'kind': 'NO_CODE_CHANGE',
                },
                'eeeeeeeeeee': {
                    '_number': 4,
                    'kind': 'NO_CHANGE',
                },
                'fffffffffff': {
                    '_number': 3,
                    'kind': 'REWORK',
                },
                'ggggggggggg': {
                    '_number': 2,
                    'kind': 'TRIVIAL_REBASE',
                },
            },
        }), None)

    result = code_coverage_util.GetEquivalentPatchsets(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 7)
    self.assertListEqual([7, 6, 5, 4, 3], result)

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testNoEquivalentPatchsets(self, mock_http_client):
    mock_http_client.return_value = (200,
                                     json.dumps({
                                         'status': 'NEW',
                                         'revisions': {
                                             'aaaaaaaaaaa': {
                                                 '_number': 8,
                                                 'kind': 'REWORK',
                                             },
                                             'bbbbbbbbbbb': {
                                                 '_number': 7,
                                                 'kind': 'NO_CODE_CHANGE',
                                             },
                                         },
                                     }), None)

    result = code_coverage_util.GetEquivalentPatchsets(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 8)
    self.assertListEqual([8], result)

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testEquivalentPatchsetsIsCached(self, mock_http_client):
    mock_http_client.return_value = (200,
                                     json.dumps({
                                         'status': 'NEW',
                                         'revisions': {
                                             'aaaaaaaaaaa': {
                                                 '_number': 8,
                                                 'kind': 'REWORK',
                                             },
                                         },
                                     }), None)

    self.assertEqual(0, mock_http_client.call_count)
    code_coverage_util.GetEquivalentPatchsets(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 8)
    self.assertEqual(1, mock_http_client.call_count)
    code_coverage_util.GetEquivalentPatchsets(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 8)
    self.assertEqual(1, mock_http_client.call_count)

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testLatestPatchsetOfSubmittedCLsIsIgnored(self, mock_http_client):
    mock_http_client.return_value = (200,
                                     json.dumps({
                                         'status': 'MERGED',
                                         'revisions': {
                                             'aaaaaaaaaaa': {
                                                 '_number': 8,
                                                 'kind': 'REWORK',
                                             },
                                             'bbbbbbbbbbb': {
                                                 '_number': 7,
                                                 'kind': 'NO_CODE_CHANGE',
                                             },
                                         },
                                     }), None)
    result = code_coverage_util.GetEquivalentPatchsets(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 8)
    self.assertListEqual([7], result)

  def testCompressLines(self):
    lines = [
        {
            'line': 102,
            'count': 4,
        },
        {
            'line': 103,
            'count': 4,
        },
        {
            'line': 107,
            'count': 4,
        },
        {
            'line': 108,
            'count': 4,
        },
    ]
    line_ranges = code_coverage_util.CompressLines(lines)
    expected_line_ranges = [
        {
            'first': 102,
            'last': 103,
            'count': 4,
        },
        {
            'first': 107,
            'last': 108,
            'count': 4,
        },
    ]

    self.assertListEqual(expected_line_ranges, line_ranges)

  def testCompressEmptyLines(self):
    lines = []
    line_ranges = code_coverage_util.CompressLines(lines)
    expected_line_ranges = []

    self.assertListEqual(expected_line_ranges, line_ranges)

  def testDecompressLineRanges(self):
    line_ranges = [
        {
            'first': 102,
            'last': 103,
            'count': 4,
        },
        {
            'first': 107,
            'last': 108,
            'count': 4,
        },
    ]

    expected_lines = [
        {
            'line': 102,
            'count': 4,
        },
        {
            'line': 103,
            'count': 4,
        },
        {
            'line': 107,
            'count': 4,
        },
        {
            'line': 108,
            'count': 4,
        },
    ]
    lines = code_coverage_util.DecompressLineRanges(line_ranges)

    self.assertListEqual(expected_lines, lines)

  @mock.patch.object(code_coverage_util.gitiles, 'get_file_content_async')
  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testRebasePresubmitCoverageDataLinesOnly(self, mock_http_client,
                                               mock_get_file_content_async):
    revisions = {'revisions': {'1234': {'_number': 1}, '5678': {'_number': 2}}}
    patchset_dest_files = {'/COMMIT_MSG': {'status': 'A'}, 'base/test.cc': {}}
    file_content_src = '1\n2\n3\n'
    file_content_dest = '0 added\n1\n2\n3 changed\n'
    mock_http_client.side_effect = [
        (200, ')]}\'' + json.dumps(revisions), None),
        (200, ')]}\'' + json.dumps(patchset_dest_files), None),
    ]

    mock_get_file_content_async.side_effect = [
        _CreateNDBFuture(file_content_src),
        _CreateNDBFuture(file_content_dest),
    ]

    coverage_data_src = [{
        'path': '//base/test.cc',
        'lines': [{
            'first': 1,
            'last': 3,
            'count': 10,
        }]
    }]
    rebased_coverage_data = (
        code_coverage_util.RebasePresubmitCoverageDataBetweenPatchsets(
            host='chromium-review.googlesource.com',
            project='chromium/src',
            change=12345,
            patchset_src=1,
            patchset_dest=2,
            coverage_data_src=coverage_data_src))

    self.assertListEqual([{
        'lines': [{
            'count': 10,
            'first': 2,
            'last': 3,
        }],
        'path': '//base/test.cc',
    }], rebased_coverage_data)

  @mock.patch.object(code_coverage_util.gitiles, 'get_file_content_async')
  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testRebasePresubmitCoverageDataLinesAndBlocks(
      self, mock_http_client, mock_get_file_content_async):
    revisions = {'revisions': {'1234': {'_number': 1}, '5678': {'_number': 2}}}
    patchset_dest_files = {'/COMMIT_MSG': {'status': 'A'}, 'base/test.cc': {}}
    file_content_src = '1\n2\n3\n'
    file_content_dest = '0 added\n1\n2\n3 changed\n'
    mock_http_client.side_effect = [
        (200, ')]}\'' + json.dumps(revisions), None),
        (200, ')]}\'' + json.dumps(patchset_dest_files), None),
    ]

    mock_get_file_content_async.side_effect = [
        _CreateNDBFuture(file_content_src),
        _CreateNDBFuture(file_content_dest),
    ]

    coverage_data_src = [{
        'path':
            '//base/test.cc',
        'lines': [{
            'first': 1,
            'last': 3,
            'count': 10,
        }],
        'uncovered_blocks': [{
            'line': 2,
            'ranges': [{
                'first': 18,
                'last': 24,
            }]
        }],
    }]
    rebased_coverage_data = (
        code_coverage_util.RebasePresubmitCoverageDataBetweenPatchsets(
            host='chromium-review.googlesource.com',
            project='chromium/src',
            change=12345,
            patchset_src=1,
            patchset_dest=2,
            coverage_data_src=coverage_data_src))

    self.assertListEqual([{
        'line': 3,
        'ranges': [{
            'first': 18,
            'last': 24
        }]
    }], rebased_coverage_data[0]['uncovered_blocks'])

  def testCalculateAbsolutePercentages(self):
    coverage_data = [{
        'path':
            '//base/test.cc',
        'lines': [
            {
                'first': 1,
                'last': 3,
                'count': 10,
            },
            {
                'first': 4,
                'last': 6,
                'count': 0,
            },
        ]
    }]
    results = code_coverage_util.CalculateAbsolutePercentages(coverage_data)
    expected_results = [
        CoveragePercentage(
            path='//base/test.cc', total_lines=6, covered_lines=3)
    ]
    self.assertEqual(1, len(results))
    self.assertListEqual(expected_results, results)

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testCalculateIncrementalPercentages(self, mock_http_client):
    revisions = {'revisions': {'1234': {'_number': 1}}}
    diff = textwrap.dedent('''\
        From cb98d2c12f258d0121c3e415f4c63e6dd5511f83 Mon Sep 17 00:00:00 2001
        From: Some One <someone@chromium.org>
        Date: Tue, 11 Dec 2018 14:47:11 -0800
        Subject: Some CL for Testing

        Change-Id: I503907407fd941fe2539eb29be3a5ac57e393623
        ---

        diff --git a/base/test.cc b/base/test.cc
        index 21cefcc4..b33e680 100644
        --- a/base/test.cc
        +++ b/base/test.cc
        @@ -1,6 +1,6 @@
         line 1
         line 2
        -line 3
        -line 4
        +line 3 changed
        +line 4 changed
         line 5
         line 6''')

    mock_http_client.side_effect = [
        (200, ')]}\'' + json.dumps(revisions), None),
        (200, base64.b64encode(diff), None),
    ]

    coverage_data = [{
        'path':
            '//base/test.cc',
        'lines': [
            {
                'first': 1,
                'last': 3,
                'count': 10,
            },
            {
                'first': 4,
                'last': 6,
                'count': 0,
            },
        ]
    }]

    results = code_coverage_util.CalculateIncrementalPercentages(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 1,
        coverage_data)
    expected_results = [
        CoveragePercentage(
            path='//base/test.cc', total_lines=2, covered_lines=1)
    ]
    self.assertEqual(1, len(results))
    self.assertListEqual(expected_results, results)

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testCalculateIncrementalPercentagesZeroTotalLines(self, mock_http_client):
    revisions = {'revisions': {'1234': {'_number': 1}}}
    diff = textwrap.dedent('''\
        diff --git a/base/test.cc b/base/test.cc
        index 21cefcc4..b33e680 100644
        --- a/base/test.cc
        +++ b/base/test.cc
        @@ -1,2 +1,1 @@
         line 1
        -line 2''')

    mock_http_client.side_effect = [
        (200, ')]}\'' + json.dumps(revisions), None),
        (200, base64.b64encode(diff), None),
    ]

    coverage_data = [{
        'path': '//base/test.cc',
        'lines': [{
            'first': 1,
            'last': 3,
            'count': 10,
        },]
    }]

    results = code_coverage_util.CalculateIncrementalPercentages(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 1,
        coverage_data)
    self.assertEqual(0, len(results))

  # Tests the scenario when two patchsets have different set of changed files
  # Even when they're traivial rebase away.
  @mock.patch.object(code_coverage_util.gitiles, 'get_file_content_async')
  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testRebasePresubmitCoverageDataFileIsDroped(self, mock_http_client,
                                                  mock_get_file_content_async):
    revisions = {'revisions': {'1234': {'_number': 1}, '5678': {'_number': 2}}}
    patchset_dest_files = {'/COMMIT_MSG': {'status': 'A'}, 'base/test1.cc': {}}
    file_content_src = '1\n2\n3\n'
    file_content_dest = '0 added\n1\n2\n3 changed\n'
    mock_http_client.side_effect = [
        (200, ')]}\'' + json.dumps(revisions), None),
        (200, ')]}\'' + json.dumps(patchset_dest_files), None),
    ]

    mock_get_file_content_async.side_effect = [
        _CreateNDBFuture(file_content_src),
        _CreateNDBFuture(file_content_dest),
    ]

    coverage_data_src = [
        {
            'path': '//base/test1.cc',
            'lines': [{
                'first': 1,
                'last': 3,
                'count': 10,
            }]
        },
        {
            'path': '//base/test2.cc',
            'lines': [{
                'first': 7,
                'last': 9,
                'count': 20,
            }]
        },
    ]
    rebased_coverage_data = (
        code_coverage_util.RebasePresubmitCoverageDataBetweenPatchsets(
            host='chromium-review.googlesource.com',
            project='chromium/src',
            change=12345,
            patchset_src=1,
            patchset_dest=2,
            coverage_data_src=coverage_data_src))

    self.assertEqual(1, len(rebased_coverage_data))
    self.assertEqual('//base/test1.cc', rebased_coverage_data[0]['path'])
