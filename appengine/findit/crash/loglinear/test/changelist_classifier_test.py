# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import logging
import math

from common.dependency import Dependency
from common.dependency import DependencyRoll
from crash.crash_report import CrashReport
from crash.loglinear.changelist_classifier import LogLinearChangelistClassifier
from crash.loglinear.changelist_features.touch_crashed_file_meta import (
    TouchCrashedFileMetaFeature)
from crash.loglinear.feature import MetaFeatureValue
from crash.loglinear.feature import WrapperMetaFeature
from crash.loglinear.weight import Weight
from crash.loglinear.weight import MetaWeight
from crash.suspect import Suspect
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.crash_test_suite import CrashTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.gitiles_repository import GitilesRepository
from libs.math import logarithms as lmath

DUMMY_CHANGELOG1 = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
        'name': 'example@chromium.org',
    },
    'message': 'dummy',
    'commit_position': 175900,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'a.cc',
            'old_path': None,
        },
    ],
    'commit_url': 'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})

DUMMY_CHANGELOG2 = ChangeLog.FromDict({
    'author': {
        'name': 'example@chromium.org',
        'email': 'example@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'example@chromium.org',
        'email': 'example@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175976,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'f0.cc',
            'old_path': 'b/f0.cc'
        },
    ],
    'commit_url': 'https://repo.test/+/2',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '2',
    'reverted_revision': '1'
})

DUMMY_CHANGELOG3 = ChangeLog.FromDict({
    'author': {
        'name': 'e@chromium.org',
        'email': 'e@chromium.org',
        'time': 'Thu Apr 1 21:24:43 2016',
    },
    'committer': {
        'name': 'example@chromium.org',
        'email': 'e@chromium.org',
        'time': 'Thu Apr 1 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 176000,
    'touched_files': [
        {
            'change_type': 'modify',
            'new_path': 'f.cc',
            'old_path': 'f.cc'
        },
        {
            'change_type': 'delete',
            'new_path': None,
            'old_path': 'f1.cc'
        },
    ],
    'commit_url': 'https://repo.test/+/3',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '3',
    'reverted_revision': '0'
})

DUMMY_CALLSTACKS = [
    CallStack(0, [], CallStackFormatType.DEFAULT, LanguageType.CPP),
    CallStack(1, [], CallStackFormatType.DEFAULT, LanguageType.CPP)]
DUMMY_REPORT = CrashReport(
    None, None, None, Stacktrace(DUMMY_CALLSTACKS, DUMMY_CALLSTACKS[0]),
    (None, None), None, None)


class LogLinearChangelistClassifierTest(CrashTestSuite):
  """Tests ``LogLinearChangelistClassifier`` class."""

  def setUp(self):
    super(LogLinearChangelistClassifierTest, self).setUp()
    meta_weight = MetaWeight({
        'TouchCrashedFileMeta': MetaWeight({
            'MinDistance': Weight(1.),
            'TopFrameIndex': Weight(1.),
            'TouchCrashedFile': Weight(1.),
        })
    })
    get_repository = GitilesRepository.Factory(self.GetMockHttpClient())
    meta_feature = WrapperMetaFeature(
        [TouchCrashedFileMetaFeature(get_repository)])

    self.changelist_classifier = LogLinearChangelistClassifier(
        get_repository, meta_feature, meta_weight)

  def testCallFailedFindingSuspects(self):
    """Tests that ``__call__`` method failed to find suspects."""
    self.mock(self.changelist_classifier, 'GenerateSuspects', lambda *_: [])
    suspects = self.changelist_classifier(DUMMY_REPORT)
    self.assertListEqual(suspects, [])

  def testCallFindsSuspects(self):
    """Tests that ``__call__`` method finds suspects."""
    suspect1 = Suspect(DUMMY_CHANGELOG1, 'src/')
    suspect2 = Suspect(DUMMY_CHANGELOG2, 'src/')

    self.mock(self.changelist_classifier, 'GenerateSuspects',
              lambda *_: [suspect1, suspect2])
    self.mock(self.changelist_classifier, 'RankSuspects',
              lambda report, suspects: [suspects[0]])
    suspects = self.changelist_classifier(DUMMY_REPORT)

    expected_suspects = [suspect1.ToDict()]
    self.assertListEqual([suspect.ToDict() for suspect in suspects],
                         expected_suspects)

  def testGenerateSuspectsFilterReverted(self):
    """Tests ``GenerateSuspects`` method."""
    dep_roll = DependencyRoll('src/', 'https://repo', 'rev1', 'rev5')
    report = DUMMY_REPORT._replace(dependency_rolls={dep_roll.path: dep_roll})
    self.mock(GitilesRepository, 'GetChangeLogs',
              lambda *_: [DUMMY_CHANGELOG1, DUMMY_CHANGELOG2, DUMMY_CHANGELOG3])

    suspects = self.changelist_classifier.GenerateSuspects(report)
    self.assertListEqual(suspects, [])

  def testRankSuspectsAllLogZeros(self):
    """Tests ``RankSuspects`` method."""
    self.mock(self.changelist_classifier._model, 'Features',
              lambda _: lambda _: MetaFeatureValue('dummy', {}))
    suspect1 = Suspect(DUMMY_CHANGELOG1, 'src/')
    suspect2 = Suspect(DUMMY_CHANGELOG2, 'src/')

    self.mock(self.changelist_classifier._model, 'Score',
              lambda _: lambda _: lmath.LOG_ZERO)
    suspects = self.changelist_classifier.RankSuspects(DUMMY_REPORT,
                                                       [suspect1, suspect2])
    self.assertEqual(suspects, [])

  def testRankSuspects(self):
    """Tests ``RankSuspects`` method."""
    self.mock(self.changelist_classifier._model, 'Features',
              lambda _: lambda _: MetaFeatureValue('dummy', {}))

    suspect = Suspect(DUMMY_CHANGELOG1, 'src/')
    self.mock(self.changelist_classifier._model, 'Score',
              lambda _: lambda _: 1.0)
    suspects = self.changelist_classifier.RankSuspects(DUMMY_REPORT,
                                                       [suspect])
    self.assertEqual(suspects[0].ToDict(), suspect.ToDict())
