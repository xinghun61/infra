# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import os

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_report import CrashReport
from analysis.keyword_extractor import FilePathExtractor
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from analysis.type_enums import CallStackFormatType
from analysis.type_enums import LanguageType


class FilePathExtractorTest(AnalysisTestCase):

  def testCall(self):
    file_paths = set(['a.cc', 'b.cc', 'c.cc'])
    frames = []
    for index, file_path in enumerate(file_paths):
      frames.append(StackFrame(index, 'src/', 'func', file_path,
                               os.path.join('src/', file_path), [index],
                               'https://repo'))
    callstacks = [
        CallStack(0, frames, CallStackFormatType.DEFAULT, LanguageType.CPP)
    ]
    crash_report = CrashReport(
        None, None, None, Stacktrace(callstacks, callstacks[0]),
        (None, None), None, None)

    file_path_extractor = FilePathExtractor()
    keywords = file_path_extractor(crash_report)
    expected_keywords = [
        os.path.join('src/', file_path) for file_path in file_paths]
    self.assertSetEqual(set(keywords.keys()), set(expected_keywords))
