# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import logging
import math
import pprint

from common.dependency import Dependency
from common.dependency import DependencyRoll
from common.chrome_dependency_fetcher import ChromeDependencyFetcher
import crash.changelist_classifier as scorer_changelist_classifier
from crash.crash_report import CrashReport
from crash.loglinear.changelist_classifier import LogLinearChangelistClassifier
from crash.loglinear.changelist_features.touch_crashed_file_meta import (
    TouchCrashedFileMetaFeature)
from crash.loglinear.feature import WrapperMetaFeature
from crash.loglinear.weight import Weight
from crash.loglinear.weight import MetaWeight
from crash.suspect import AnalysisInfo
from crash.suspect import Suspect
from crash.suspect import StackInfo
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.crash_test_suite import CrashTestSuite
from crash.type_enums import CallStackFormatType
from crash.type_enums import LanguageType
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.gitiles_repository import GitilesRepository

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
    'reverted_revision': None
})

DUMMY_CALLSTACKS = [
    CallStack(0, [], CallStackFormatType.DEFAULT, LanguageType.CPP),
    CallStack(1, [], CallStackFormatType.DEFAULT, LanguageType.CPP)]
DUMMY_REPORT = CrashReport(
    None, None, None, Stacktrace(DUMMY_CALLSTACKS, DUMMY_CALLSTACKS[0]),
    (None, None), None, None)


class LogLinearChangelistClassifierTest(CrashTestSuite):

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

  # TODO(http://crbug.com/659346): why do these mocks give coverage
  # failures? That's almost surely hiding a bug in the tests themselves.
  def testFindItForCrashNoRegressionRange(self): # pragma: no cover
    # N.B., for this one test we really do want regression_range=None.
    report = CrashReport(None, None, None, Stacktrace(DUMMY_CALLSTACKS,
                                                      DUMMY_CALLSTACKS[0]),
                         None, {}, {})
    self.assertListEqual(self.changelist_classifier(report), [])

  def testFindItForCrashNoMatchFound(self):
    self.mock(scorer_changelist_classifier, 'FindSuspects', lambda *_: [])
    self.assertListEqual(self.changelist_classifier(DUMMY_REPORT), [])

    self.mock(scorer_changelist_classifier, 'FindSuspects', lambda *_: None)
    self.assertListEqual(self.changelist_classifier(DUMMY_REPORT), [])

  def testFindItForCrash(self):
    suspect1 = Suspect(DUMMY_CHANGELOG1, 'src/')
    suspect2 = Suspect(DUMMY_CHANGELOG3, 'src/')

    a_cc_blame = Blame('6', 'src/')
    a_cc_blame.AddRegions([Region(0, 10, suspect1.changelog.revision,
                                  suspect1.changelog.author.name,
                                  suspect1.changelog.author.email,
                                  suspect1.changelog.author.time)])
    f_cc_blame = Blame('6', 'src/')
    f_cc_blame.AddRegions([Region(21, 10, suspect2.changelog.revision,
                                  suspect2.changelog.author.name,
                                  suspect2.changelog.author.email,
                                  suspect2.changelog.author.time)])
    url_to_blame = {'6/a.cc': a_cc_blame,
                    '6/f.cc': f_cc_blame}

    def _MockGetBlame(_, path, revision):
      revision_path = '%s/%s' % (revision, path)
      return url_to_blame.get(revision_path)

    self.mock(GitilesRepository, 'GetBlame', _MockGetBlame)
    self.mock(scorer_changelist_classifier,
              'GetChangeLogsForFilesGroupedByDeps',
              lambda *_: (None, None))
    self.mock(scorer_changelist_classifier, 'FindSuspects',
              lambda *_: [suspect1, suspect2])
    frame1 = StackFrame(0, 'src/', 'func', 'a.cc', 'src/a.cc', [1])
    frame2 = StackFrame(1, 'src/', 'func', 'a.cc', 'src/a.cc', [7])
    frame3 = StackFrame(15, 'src/', 'func', 'f.cc', 'src/f.cc', [1])
    frame4 = StackFrame(3, 'src/dep1', 'func', 'f.cc', 'src/dep1/f.cc', [1])
    stacks = [CallStack(0, frame_list=[frame1, frame2, frame3, frame4])]
    stacktrace = Stacktrace(stacks, stacks[0])
    report = CrashReport(
        '6', 'sig', 'win', stacktrace, ('0', '4'),
        {'src/': Dependency('src/', 'https://repo', '6')},
        {'src/': DependencyRoll('src/', 'https://repo', '0', '4')} )

    suspects = self.changelist_classifier(report)
    self.assertTrue(suspects,
                    'Expected suspects, but the classifier didn\'t return any')

    expected_suspects = [
        {
            'author': 'r@chromium.org',
            'changed_files': [
                {
                    'blame_url': None,
                    'file': 'a.cc',
                    'info': ('Distance from touched lines and crashed lines is '
                             '0, in frame #0')
                }
            ],
            'confidence': 0.,
            'project_path': 'src/',
            'reasons': ('MinDistance: 0.000000 -- Minimum distance is '
                        '0\nTopFrameIndex: 0.000000 -- Top frame is #0\n'
                        'TouchCrashedFile: 0.000000 -- Touched files - a.cc'),
            'review_url': 'https://codereview.chromium.org/3281',
            'revision': '1',
            'time': 'Thu Mar 31 21:24:43 2016',
            'url': 'https://repo.test/+/1'
        },
    ]
    self.assertListEqual([suspect.ToDict() for suspect in suspects],
                         expected_suspects)
