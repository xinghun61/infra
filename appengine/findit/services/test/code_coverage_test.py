# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import mock

from services import code_coverage
from waterfall.test.wf_testcase import WaterfallTestCase


class CodeCoverageTest(WaterfallTestCase):

  @mock.patch.object(code_coverage.FinditHttpClient, 'Get')
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

    result = code_coverage.GetEquivalentPatchsets(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 7)
    self.assertListEqual([7, 6, 5, 4, 3], result)

  @mock.patch.object(code_coverage.FinditHttpClient, 'Get')
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

    result = code_coverage.GetEquivalentPatchsets(
        'chromium-review.googlesource.com', 'chromium/src', 12345, 8)
    self.assertListEqual([8], result)

  @mock.patch.object(code_coverage.FinditHttpClient, 'Get')
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
    code_coverage.GetEquivalentPatchsets('chromium-review.googlesource.com',
                                         'chromium/src', 12345, 8)
    self.assertEqual(1, mock_http_client.call_count)
    code_coverage.GetEquivalentPatchsets('chromium-review.googlesource.com',
                                         'chromium/src', 12345, 8)
    self.assertEqual(1, mock_http_client.call_count)

  @mock.patch.object(code_coverage.FinditHttpClient, 'Get')
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
    result = code_coverage.GetEquivalentPatchsets(
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
    line_ranges = code_coverage.CompressLines(lines)
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
    line_ranges = code_coverage.CompressLines(lines)
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
    lines = code_coverage.DecompressLineRanges(line_ranges)

    self.assertListEqual(expected_lines, lines)
