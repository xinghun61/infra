# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.analysis_testcase import AnalysisTestCase
from analysis.component_classifier import Component
from analysis.component_classifier import ComponentClassifier
from analysis.crash_report import CrashReport
from analysis.linear.changelist_features.touch_crashed_component import (
    TouchCrashedComponentFeature)
from analysis.suspect import Suspect
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
from libs.gitiles.gitiles_repository import GitilesRepository

COMPONENT_CONFIG = {
      'component_info': [
          {
              'dirs': ['src/comp1'],
              'component': 'Comp1>Dummy'
          },
          {
              'dirs': ['src/comp2'],
              'function': 'func2.*',
              'component': 'Comp2>Dummy',
              'team': 'comp2-team'
          }
      ],
      'top_n': 4
  }

_DUMMY_CHANGELOG = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'example@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175900,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'comp1/a.cc',
            'old_path': None,
        },
    ],
    'commit_url': 'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})

_MOCK_REPO_TO_DEP_PATH = {
    'https://chromium.git': 'src',
    'https://chromium.v8.git': 'src/v8',
}


class TouchCrashedComponentFeatureTest(AnalysisTestCase):
  """Tests ``TouchCrashedComponentFeature``."""

  def setUp(self):
    super(TouchCrashedComponentFeatureTest, self).setUp()
    components = [Component(info['component'], info['dirs'],
                            info.get('function'), info.get('team'))
                  for info in COMPONENT_CONFIG['component_info']]
    # Only construct the classifier once, rather than making a new one every
    # time we call a method on it.
    self.classifier = ComponentClassifier(components, COMPONENT_CONFIG['top_n'],
                                          _MOCK_REPO_TO_DEP_PATH)
    self.feature = TouchCrashedComponentFeature(self.classifier)

  def testFeatureValueIsOneWhenThereIsMatchedComponent(self):
    """Test that feature value is 1 when there no matched component."""
    # One dummy component in config is ['src/comp1.*', '', 'Comp1>Dummy'].
    frame1 = StackFrame(0, 'src/', 'func', 'comp1/f.cc',
                        'src/comp1/f.cc', [2, 3], 'h://repo')
    stack = CallStack(0, frame_list=[frame1])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', '8')}
    dep_rolls = {'src/': DependencyRoll('src/', 'h://repo', '2', '6')}
    report = CrashReport('8', 'sig', 'linux', stack_trace,
                         ('2', '6'), deps, dep_rolls)
    suspect = Suspect(_DUMMY_CHANGELOG, 'src/')
    feature_value = self.feature(report)(suspect)
    self.assertEqual(1.0, feature_value.value)

  def testFeatureValueIsZeroWhenNoMatchedComponent(self):
    """Test that the feature returns 0 when there no matched component."""
    frame = StackFrame(0, 'src/', 'func', 'dir/f.cc',
                        'src/dir/f.cc', [2, 3], 'h://repo')
    stack = CallStack(0, frame_list=[frame])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', '8')}
    dep_rolls = {'src/': DependencyRoll('src/', 'h://repo', '2', '6')}
    report = CrashReport('8', 'sig', 'linux', stack_trace,
                         ('2', '6'), deps, dep_rolls)
    suspect = Suspect(_DUMMY_CHANGELOG, 'src/')
    feature_value = self.feature(report)(suspect)
    self.assertEqual(0.0, feature_value.value)
