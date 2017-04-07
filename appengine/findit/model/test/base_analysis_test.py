# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
import unittest

from libs import analysis_status
from model.base_analysis import BaseAnalysis

from google.appengine.ext import ndb


class _DummyModel(BaseAnalysis):

  @staticmethod
  def Create(key_string):
    key = ndb.Key('_DummyModel', key_string)
    return _DummyModel(key=key)

# Complains when we modify properties of DummyModel
# pylint: disable=attribute-defined-outside-init
class BaseModelTest(unittest.TestCase):

  def setUp(self):
    self.dummy_model = _DummyModel.Create('dummy_key')

  def testBaseAnalysisStatusIsCompleted(self):
    for status in (analysis_status.COMPLETED, analysis_status.ERROR):
      self.dummy_model.status = status
      self.assertTrue(self.dummy_model.completed)

  def testBaseAnalysisStatusIsNotCompleted(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING):
      self.dummy_model.status = status
      self.assertFalse(self.dummy_model.completed)

  def testBaseAnalysisDurationWhenNotCompleted(self):
    self.dummy_model.status = analysis_status.RUNNING
    self.assertIsNone(self.dummy_model.duration)

  def testBaseAnalysisDurationWhenStartTimeNotSet(self):
    self.dummy_model.status = analysis_status.COMPLETED
    self.dummy_model.end_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    self.assertIsNone(self.dummy_model.duration)

  def testBaseAnalysisDurationWhenEndTimeNotSet(self):
    self.dummy_model.status = analysis_status.COMPLETED
    self.dummy_model.start_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    self.assertIsNone(self.dummy_model.duration)

  def testBaseAnalysisDurationWhenCompleted(self):

    self.dummy_model.status = analysis_status.COMPLETED
    self.dummy_model.start_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    self.dummy_model.end_time = datetime(2015, 07, 30, 21, 16, 15, 50)
    self.assertEqual(45, self.dummy_model.duration)

  def testBaseAnalysisStatusIsFailed(self):
    self.dummy_model.status = analysis_status.ERROR
    self.assertTrue(self.dummy_model.failed)

  def testBaseAnalysisStatusIsNotFailed(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED):

      self.dummy_model.status = status
      self.assertFalse(self.dummy_model.failed)

  def testBaseAnalysisStatusDescriptionPending(self):
    self.dummy_model.status = analysis_status.PENDING
    self.assertEqual('Pending', self.dummy_model.status_description)

  def testBaseAnalysisStatusDescriptionRunning(self):
    self.dummy_model.status = analysis_status.RUNNING
    self.assertEqual('Running', self.dummy_model.status_description)

  def testBaseAnalysisStatusDescriptionCompleted(self):
    self.dummy_model.status = analysis_status.COMPLETED
    self.assertEqual('Completed', self.dummy_model.status_description)

  def testBaseAnalysisStatusDescriptionError(self):
    self.dummy_model.status = analysis_status.ERROR
    self.assertEqual('Error', self.dummy_model.status_description)

  def testReset(self):
    self.dummy_model.pipeline_status_path = 'a'
    self.dummy_model.status = analysis_status.COMPLETED
    self.dummy_model.request_time = datetime.now()
    self.dummy_model.start_time = datetime.now()
    self.dummy_model.end_time = datetime.now()
    self.dummy_model.version = 'a'
    self.dummy_model.Reset()
    self.assertIsNone(self.dummy_model.pipeline_status_path)
    self.assertEqual(analysis_status.PENDING, self.dummy_model.status)
    self.assertIsNone(self.dummy_model.request_time)
    self.assertIsNone(self.dummy_model.start_time)
    self.assertIsNone(self.dummy_model.end_time)
    self.assertIsNone(self.dummy_model.version)
