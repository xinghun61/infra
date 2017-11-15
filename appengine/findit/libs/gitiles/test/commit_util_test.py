# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import StringIO
from testing_utils import testing
import textwrap
import urllib2

from libs.gitiles import commit_util


class CodeReviewUtilTest(testing.AppengineTestCase):

  def testExtractChangeInfo(self):
    testcases = [{
        'message': 'balabala...\n'
                   '\n'
                   'BUG=604502\n'
                   '\n'
                   'Review-Url: https://codereview.chromium.org/1927593004\n'
                   'Cr-Commit-Position: refs/heads/master@{#390254}\n',
        'commit_position': 390254,
        'code_review_url': 'https://codereview.chromium.org/1927593004',
        'change_id': '1927593004',
        'host': 'codereview.chromium.org',
    }, {
        'message': 'balabala...\n'
                   '\n'
                   'BUG=409934\n'
                   '\n'
                   'Review URL: https://codereview.chromium.org/547753003\n'
                   '\n'
                   'Cr-Commit-Position: refs/heads/master@{#293661}',
        'commit_position': 293661,
        'code_review_url': 'https://codereview.chromium.org/547753003',
        'change_id': '547753003',
        'host': 'codereview.chromium.org',
    }, {
        'message': 'Review URL: https://codereview.chromium.org/469523002\n'
                   '\n'
                   'Cr-Commit-Position: refs/heads/master@{#289120}',
        'commit_position': 289120,
        'code_review_url': 'https://codereview.chromium.org/469523002',
        'change_id': '469523002',
        'host': 'codereview.chromium.org',
    }, {
        'message': 'balabala...\n'
                   '\n'
                   'balabala...\n'
                   '\n'
                   'R=test4@chromium.org\n'
                   '\n'
                   'Review URL: https://codereview.chromium.org/469523002\n',
        'commit_position': None,
        'code_review_url': 'https://codereview.chromium.org/469523002',
        'change_id': '469523002',
        'host': 'codereview.chromium.org',
    }, {
        'message': None,
        'commit_position': None,
        'code_review_url': None,
        'change_id': None,
        'host': None,
    }, {
        'message': 'abc',
        'commit_position': None,
        'code_review_url': None,
        'change_id': None,
        'host': None,
    }, {
        'message':
            'balabala...\n'
            '\n'
            'balabala...\n'
            '\n'
            'R=test4@chromium.org\n'
            '\n'
            'Change-Id: Iaa54f242b5b2fa10870503ef88291b9422cb47ca\n'
            'Reviewed-on: https://chromium-review.googlesource.com/45425\n'
            'Cr-Commit-Position: refs/heads/master@{#456563}',
        'commit_position': 456563,
        'code_review_url': 'https://chromium-review.googlesource.com/q/'
                           'Iaa54f242b5b2fa10870503ef88291b9422cb47ca',
        'change_id': 'Iaa54f242b5b2fa10870503ef88291b9422cb47ca',
        'host': 'chromium-review.googlesource.com',
    }]

    for testcase in testcases:
      change_info = commit_util.ExtractChangeInfo(testcase['message'])
      self.assertEqual(
          change_info.get('commit_position'), testcase['commit_position'])
      self.assertEqual(
          change_info.get('code_review_url'), testcase['code_review_url'])
      self.assertEqual(change_info.get('host'), testcase['host'])
      self.assertEqual(change_info.get('change_id'), testcase['change_id'])

  def testNormalizeEmail(self):
    self.assertEqual(
        commit_util.NormalizeEmail(
            'test@chromium.org@bbb929c8-8fbe-4397-9dbb-9b2b20218538'),
        'test@chromium.org')

  def testGetRevertedRevision(self):
    message = ('Revert of test1\n\nReason for revert:\nrevert test1\n\n'
               'Original issue\'s description:\n> test 1\n>\n'
               '> description of test 1.\n>\n> BUG=none\n> TEST=none\n'
               '> R=test@chromium.org\n> TBR=test@chromium.org\n>\n'
               '> Committed: https://chromium.googlesource.com/chromium/src/+/'
               'c9cc182781484f9010f062859cda048afefefefe\n'
               '> Cr-Commit-Position: refs/heads/master@{#341992}\n\n'
               'TBR=test@chromium.org\nNOPRESUBMIT=true\nNOTREECHECKS=true\n'
               'NOTRY=true\nBUG=none\n\n'
               'Review URL: https://codereview.chromium.org/1278653002\n\n'
               'Cr-Commit-Position: refs/heads/master@{#342013}\n')

    reverted_revision = commit_util.GetRevertedRevision(message)
    self.assertEqual('c9cc182781484f9010f062859cda048afefefefe',
                     reverted_revision)

  def testGetRevertedRevisionEmptyMessage(self):
    self.assertIsNone(commit_util.GetRevertedRevision(''))

  def testGetRevertedRevisionRevertOfRevert(self):
    message = (
        'Revert of Revert\n\nReason for revert:\nRevert of revert\n\n'
        'Original issue\'s description:\n> test case of revert of revert\n>\n'
        '> Reason for revert:\n> reason\n>\n> Original issue\'s description:\n'
        '> > base cl\n> >\n> > R=kalman\n> > BUG=424661\n> >\n'
        '> > Committed: https://crrev.com/34ea66b8ac1d56dadd670431063857ffdd\n'
        '> > Cr-Commit-Position: refs/heads/master@{#326953}\n>\n'
        '> TBR=test@chromium.org\n> NOPRESUBMIT=true\n'
        '> NOTREECHECKS=true\n> NOTRY=true\n> BUG=424661\n>\n'
        '> Committed: https://crrev.com/76a7e3446188256ca240dc31f78de29511a'
        '2c322\n'
        '> Cr-Commit-Position: refs/heads/master@{#327021}\n\n'
        'TBR=test@chromium.org\nNOPRESUBMIT=true\n'
        'NOTREECHECKS=true\nNOTRY=true\nBUG=424661\n\n'
        'Review URL: https://codereview.chromium.org/1161773008\n\n'
        'Cr-Commit-Position: refs/heads/master@{#332062}\n')

    reverted_revision = commit_util.GetRevertedRevision(message)
    self.assertEqual('76a7e3446188256ca240dc31f78de29511a2c322',
                     reverted_revision)

  def testGetRevertedRevisionNoRevertedCL(self):
    message = ('Test for not revert cl\n\n'
               'TBR=test@chromium.org\nNOPRESUBMIT=true\n'
               'NOTREECHECKS=true\nNOTRY=true\nBUG=424661\n\n'
               'Review URL: https://codereview.chromium.org/1161773008\n\n'
               'Cr-Commit-Position: refs/heads/master@{#332062}\n')

    reverted_revision = commit_util.GetRevertedRevision(message)
    self.assertIsNone(reverted_revision)

  def testDistanceBetweenLineRangesErrors(self):
    self.assertRaises(
        ValueError,
        lambda: commit_util.DistanceBetweenLineRanges((1, 0), (2, 3)))
    self.assertRaises(
        ValueError,
        lambda: commit_util.DistanceBetweenLineRanges((2, 3), (1, 0)))

  def testDistanceBetweenLineRangesSuccesses(self):
    tests = [
        (2, (1, 2), (4, 5)),
        (0, (1, 3), (2, 4)),
        (0, (1, 4), (2, 3)),
    ]

    for expected_distance, range1, range2 in tests:
      distance12 = commit_util.DistanceBetweenLineRanges(range1, range2)
      distance21 = commit_util.DistanceBetweenLineRanges(range2, range1)
      self.assertEqual(distance12, distance21)
      self.assertEqual(expected_distance, distance12)
