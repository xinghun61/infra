# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.pipeline_wrapper import pipeline_handlers
from crash.stacktrace import StackFrame
from crash.stacktrace import CallStack
from crash.component_classifier import Component
from crash.component_classifier import ComponentClassifier
from crash.suspect import Suspect
from crash.test.predator_testcase import PredatorTestCase
from model.crash.crash_config import CrashConfig
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo


# N.B., the call to Get() in CrashConfigComponentClassifier.__init__
# must only be executed from within the testFoo methods of
# ComponentClassifierTest. That is, we can't just do this once and for all
# when doing ComponentClassifierTest.__init__, because that'll cause some
# strange issues in mocking. But factoring it out like this so it gets
# (re)called ever time a testFoo is run, that works.
class CrashConfigComponentClassifier(ComponentClassifier):
  """A ComponentClassifier which gets its components from CrashConfig."""
  def __init__(self):
    config = CrashConfig.Get().component_classifier
    super(CrashConfigComponentClassifier, self).__init__(
        [Component(name, path, function)
            for path, function, name
            in config.get('path_function_component', [])],
        config.get('top_n', 0))


class ComponentClassifierTest(PredatorTestCase):

  def setUp(self):
    super(ComponentClassifierTest, self).setUp()
    # Only construct the cccc once, rather than making a new one every
    # time we call a method on it.
    self.cccc = CrashConfigComponentClassifier()

  def testGetClassFromStackFrame(self):
    frame = StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2])
    self.assertEqual(self.cccc.GetClassFromStackFrame(frame), 'Comp1>Dummy')

    frame = StackFrame(0, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [32])
    self.assertEqual(self.cccc.GetClassFromStackFrame(frame), 'Comp2>Dummy')

    frame = StackFrame(0, 'src/', 'no_func', 'comp2.cc', 'src/comp2.cc', [32])
    self.assertEqual(self.cccc.GetClassFromStackFrame(frame), '')

    frame = StackFrame(0, 'src/', 'func2', 'a.cc', 'src/a.cc', [6])
    self.assertEqual(self.cccc.GetClassFromStackFrame(frame), '')

  def testGetClassFromSuspect(self):
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    self.assertEqual(self.cccc.GetClassFromSuspect(suspect), '')

    suspect.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }
    self.assertEqual(self.cccc.GetClassFromSuspect(suspect), 'Comp1>Dummy')

  def testClassifyCrashStack(self):
    crash_stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]),
        StackFrame(1, 'src/', 'ff', 'comp1.cc', 'src/comp1.cc', [21]),
        StackFrame(2, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [8])])

    self.assertEqual(self.cccc.Classify([], crash_stack),
                     ['Comp1>Dummy', 'Comp2>Dummy'])

  def testClassifySuspects(self):
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }

    self.assertEqual(self.cccc.Classify([suspect], CallStack(0)),
                     ['Comp1>Dummy'])

  def testClassifierDoNotHaveConfig(self):
    crash_config = CrashConfig.Get()
    crash_config.component_classifier = {}
    # N.B., we must construct a new cccc here, becasue we changed CrashConfig.
    self.cccc = CrashConfigComponentClassifier()

    crash_stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]),
        StackFrame(1, 'src/', 'ff', 'comp1.cc', 'src/comp1.cc', [21]),
        StackFrame(2, 'src/', 'func2', 'comp2.cc', 'src/comp2.cc', [8])])

    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect.file_to_stack_infos = {
        'comp1.cc': [
            (StackFrame(0, 'src/', 'func', 'comp1.cc', 'src/comp1.cc', [2]), 0)
        ]
    }

    self.assertEqual(self.cccc.Classify([suspect], crash_stack), [])

  def testGetClassFromFileChangeInfo(self):
    self.assertEqual(
        CrashConfigComponentClassifier().GetClassFromFileChangeInfo(
            FileChangeInfo.FromDict({'change_type': 'modify',
                                     'old_path': 'src/comp1.cc',
                                     'new_path': 'src/comp1.cc'})),
        'Comp1>Dummy')

  def testGetClassFromFileChangeInfoOldPath(self):
    self.assertEqual(
        CrashConfigComponentClassifier().GetClassFromFileChangeInfo(
            FileChangeInfo.FromDict({'change_type': 'delete',
                                     'old_path': 'src/comp1.cc',
                                     'new_path': ''})),
        'Comp1>Dummy')


  def testGetClassFromNoneFileChangeInfo(self):
    self.assertEqual(
        CrashConfigComponentClassifier().GetClassFromFileChangeInfo(None),
        None)

  def testGetClassFromChangeFileInfoNoMapping(self):
    self.assertEqual(
        CrashConfigComponentClassifier().GetClassFromFileChangeInfo(
            FileChangeInfo.FromDict({'change_type':'modify',
                                     'old_path':'file',
                                     'new_path':'file'})),'')

  def testGetClassFromChangeFileInfoNoMappingOldPath(self):
    self.assertEqual(
        CrashConfigComponentClassifier().GetClassFromFileChangeInfo(
            FileChangeInfo.FromDict({'change_type':'rename',
                                     'old_path':'old_file',
                                     'new_path':'new_file'})),'')

  def testClassifyChangeLog(self):
     change_log = ChangeLog.FromDict({
         'author': {
             'name': 'a',
             'email': 'b@email.com',
             'time': '2014-08-13 00:53:12',
         },
         'committer': {
             'name': 'c',
             'email': 'd@email.com',
             'time': '2014-08-14 00:53:12',
         },
         'revision': 'aaaa',
         'commit_position': 1111,
         'touched_files': [
             {
                 'change_type': 'copy',
                 'old_path': 'file',
                 'new_path': 'src/comp2.cc'
             },
             {
                 'change_type': 'modify',
                 'old_path': 'src/comp2.cc',
                 'new_path': 'src/comp2.cc'
             },
             {
                 'change_type': 'modify',
                 'old_path': 'src/comp1.cc',
                 'new_path': 'src/comp1.cc'
             }
         ],
         'message': 'blabla...',
         'commit_url':
         'https://chromium.googlesource.com/chromium/src/+/git_hash',
         'code_review_url': 'https://codereview.chromium.org/2222',
         'reverted_revision': '8d4a4fa6s18raf3re12tg6r'})
     self.assertEqual(
         CrashConfigComponentClassifier().ClassifyChangeLog(change_log),
         ['Comp2>Dummy', 'Comp1>Dummy'])

  def testClassifyNoneChangeLog(self):
    change_log = None
    self.assertEqual(
        CrashConfigComponentClassifier().ClassifyChangeLog(change_log),
        None)

  def testClassifyChangeLogNoMapping(self):
    change_log = ChangeLog.FromDict({
        'author': {
            'name': 'a',
            'email': 'b@email.com',
            'time': '2014-08-13 00:53:12',
        },
        'committer': {
            'name': 'c',
            'email': 'd@email.com',
            'time': '2014-08-14 00:53:12',
        },
        'revision': 'aaaa',
        'commit_position': 1111,
        'touched_files': [
            {
                'change_type': 'rename',
                'old_path': 'old_file',
                'new_path': 'new_file'
            },
            {
                'change_type': 'delete',
                'old_path': 'file',
                'new_path': 'file'
            }
        ],
        'message': 'blabla...',
        'commit_url':
        'https://chromium.googlesource.com/chromium/src/+/git_hash',
        'code_review_url': 'https://codereview.chromium.org/2222',
        'reverted_revision': '8d4a4fa6s18raf3re12tg6r'})
    self.assertEqual(
        CrashConfigComponentClassifier().ClassifyChangeLog(change_log),
        [])
