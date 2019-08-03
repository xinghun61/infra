# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock

from services.code_coverage import code_coverage_util
from waterfall.test.wf_testcase import WaterfallTestCase


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

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testRebasePresubmitCoverageDataLinesOnly(self, mock_http_client):
    revisions = {'revisions': {'1234': {'_number': 1}, '5678': {'_number': 2}}}
    file_content_src = '1\n2\n3\n'
    file_content_dest = '0 added\n1\n2\n3 changed\n'
    mock_http_client.side_effect = [
        (200, ')]}\'' + json.dumps(revisions), None),
        (200, base64.b64encode(file_content_src), None),
        (200, base64.b64encode(file_content_dest), None),
    ]

    coverage_data_src = [{
        'path': 'base/test.cc',
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
        'path': 'base/test.cc',
    }], rebased_coverage_data)

  @mock.patch.object(code_coverage_util.FinditHttpClient, 'Get')
  def testRebasePresubmitCoverageDataLinesAndBlocks(self, mock_http_client):
    revisions = {'revisions': {'1234': {'_number': 1}, '5678': {'_number': 2}}}
    file_content_src = '1\n2\n3\n'
    file_content_dest = '0 added\n1\n2\n3 changed\n'
    mock_http_client.side_effect = [
        (200, ')]}\'' + json.dumps(revisions), None),
        (200, base64.b64encode(file_content_src), None),
        (200, base64.b64encode(file_content_dest), None),
    ]

    coverage_data_src = [{
        'path':
            'base/test.cc',
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
