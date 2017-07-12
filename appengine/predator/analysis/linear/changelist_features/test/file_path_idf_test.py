# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import math

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_report import CrashReport
from analysis.crash_match import CrashedFile
from analysis.crash_match import CrashMatch
from analysis.crash_match import FrameInfo
from analysis.linear.changelist_features import file_path_idf
from analysis.stacktrace import StackFrame


class _MockInvertedIndex(namedtuple('_MockInvertedIndex', ['n_of_doc'])):
  pass


class _MockInvertedIndexTable(object):
  _TABLE = {'keyword1': _MockInvertedIndex(3),
            'keyword2': _MockInvertedIndex(9)}
  _ROOT = _MockInvertedIndex(9)

  @classmethod
  def Get(cls, keyword):
    return cls._TABLE.get(keyword)

  @classmethod
  def GetRoot(cls):
    return cls._ROOT


class FilePathIdfFeatureTest(AnalysisTestCase):
  """Tests ``FilePathIdfFeature``."""

  def setUp(self):
    super(FilePathIdfFeatureTest, self).setUp()
    self.feature = file_path_idf.FilePathIdfFeature(_MockInvertedIndexTable)

  def testLogRegressionNormalize(self):
    """Tests that ``LogRegressionNormalize`` normalizes value to [0, 1]."""
    values = [-10, -8, 0, 3, 99]
    prev_value = -100
    for value in values:
      normalized = file_path_idf.LogRegressNomalize(value)
      self.assertTrue(normalized >= 0)
      self.assertTrue(normalized <= 1)
      self.assertTrue(
          file_path_idf.LogRegressNomalize(prev_value) <= normalized)

      prev_value = value

  def testGetDocumentNumberForKeyword(self):
    """Tests that ``GetDocumentNumberForKeyword`` returns document number."""
    self.assertEqual(file_path_idf.GetDocumentNumberForKeyword(
        'dummy', _MockInvertedIndexTable), 0)
    self.assertEqual(file_path_idf.GetDocumentNumberForKeyword(
        'keyword1', _MockInvertedIndexTable), 3)
    self.assertEqual(file_path_idf.GetDocumentNumberForKeyword(
        'keyword2', _MockInvertedIndexTable), 9)

  def testGetTotalDocumentNumber(self):
    """Tests that ``GetTotalDocumentNumber`` returns document number."""
    self.assertEqual(file_path_idf.GetTotalDocumentNumber(
        _MockInvertedIndexTable), 9)

  def testComputeIdf(self):
    """Tests ``ComputeIdf`` computes idf for a keyword."""
    self.assertAlmostEqual(
        file_path_idf.ComputeIdf('dummy', _MockInvertedIndexTable),
        math.log(9 / 1.0))
    self.assertAlmostEqual(
        file_path_idf.ComputeIdf('keyword1', _MockInvertedIndexTable),
        math.log(9 / float(1 + 3)))
    self.assertAlmostEqual(
        file_path_idf.ComputeIdf('keyword2', _MockInvertedIndexTable),
        math.log(9 / float(1 + 9)))

  def testFilePathIdfFeatureNameProperty(self):
    """Tests name property of ``FilePathIdfFeature``"""
    self.assertEqual(self.feature.name, 'FilePathIdf')

  def testFilePathIdfFeatureCallForNoneMatches(self):
    """Tests ``__call__`` of ``FilePathIdfFeature`` for None matches."""
    report = CrashReport(None, None, None, None, None, None, None)
    feature_value = self.feature(report)(None, None)
    self.assertEqual(feature_value.value, 0)

  def testFilePathIdfFeatureCallForMatches(self):
    """Tests ``__call__`` of ``FilePathIdfFeature`` for non-empty matches."""
    report = CrashReport(None, None, None, None, None, None, None)
    frame1 = StackFrame(0, '', 'func', 'keyword1', 'src/keyword1',
                        [2], 'http://repo')
    frame2 = StackFrame(0, '', 'func', 'keyword2', 'src/keyword2',
                        [9], 'http://repo')
    matches = {
        CrashedFile('keyword1'): CrashMatch(
            CrashedFile('keyword1'), ['keyword1'], [FrameInfo(frame1, 0)]),
        CrashedFile('keyword2'): CrashMatch(
            CrashedFile('keyword2'), ['keyword2'], [FrameInfo(frame2, 0)])
    }

    feature_value = self.feature(report)(None, matches)
    self.assertEqual(feature_value.value, file_path_idf.LogRegressNomalize(
        math.log(9 / float(1 + 3))))
