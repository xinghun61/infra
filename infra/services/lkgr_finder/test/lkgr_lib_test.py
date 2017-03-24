#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Source file for lkgr_lib testcases."""


import datetime
import httplib2
import mock
import os
import sys
import tempfile
import unittest

from infra.services.lkgr_finder import lkgr_lib
from infra.services.lkgr_finder.status_generator import StatusGeneratorStub


# TODO(agable): Test everything else once I can import pymox.


class FetchBuilderJsonTest(unittest.TestCase):
  test_masters = {
    'master1': {
      'base_url': 'http://master.url.com',
      'builders': ['builder1', 'builder2'],
    },
  }

  @mock.patch(
      'infra.services.lkgr_finder.lkgr_lib.FetchBuilderJsonFromMilo',
      autospec=True)
  def testAllBuildersSucceeded(self, mocked_fetch):
    mocked_fetch.side_effect = iter([{'build1': 'success'}, {'build2': 'failure'}])
    build_data,failures = lkgr_lib.FetchBuildData(self.test_masters,
                                                  max_threads=1)
    self.assertEquals(failures, 0)
    self.assertEquals(len(build_data['master1']), 2)
    self.assertEquals(build_data['master1']['builder1']['build1'], 'success')
    self.assertEquals(build_data['master1']['builder2']['build2'], 'failure')

  @mock.patch(
      'infra.services.lkgr_finder.lkgr_lib.FetchBuilderJsonFromMilo',
      autospec=True)
  @mock.patch('time.sleep', return_value=None)
  def testAllBuildersFailed(self, mocked_sleep, mocked_fetch):
    mocked_fetch.side_effect = httplib2.HttpLib2Error
    build_data, failures = lkgr_lib.FetchBuildData(self.test_masters,
                                                   max_threads=1)
    self.assertEquals(failures, 2)
    self.assertEquals(build_data['master1']['builder1'], None)
    self.assertEquals(build_data['master1']['builder2'], None)

  @mock.patch(
      'infra.services.lkgr_finder.lkgr_lib.FetchBuilderJsonFromMilo',
      autospec=True)
  @mock.patch('time.sleep', return_value=None)
  def testSomeBuildersFailed(self, mocked_sleep, mocked_fetch):
    def _raise_http_err(master, builder, **kwargs):
      if builder == 'builder1':
        return {'build1': 'success'}
      raise httplib2.HttpLib2Error()
    mocked_fetch.side_effect = _raise_http_err
    build_data,failures = lkgr_lib.FetchBuildData(self.test_masters,
                                                  max_threads=1)
    self.assertEquals(failures, 1)
    self.assertEquals(len(build_data['master1']), 2)
    self.assertEquals(build_data['master1']['builder1']['build1'], 'success')
    self.assertEquals(build_data['master1']['builder2'], None)


class FindLKGRCandidateTest(unittest.TestCase):

  def setUp(self):
    self.status_stub = StatusGeneratorStub()
    self.good = lkgr_lib.STATUS.SUCCESS
    self.fail = lkgr_lib.STATUS.FAILURE
    self.keyfunc = int

  def testSimpleSucceeds(self):
    build_history = {'m1': {'b1': [(1, self.good, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 1)

  def testSimpleFails(self):
    build_history = {'m1': {'b1': [(1, self.fail, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testModerateSuccess(self):
    build_history = {
        'm1': {'b1': [(1, self.good, 1)]},
        'm2': {'b2': [(1, self.good, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 1)

  def testModerateFailsOne(self):
    build_history = {
        'm1': {'b1': [(1, self.good, 1)]},
        'm2': {'b2': [(1, self.fail, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testModerateFailsTwo(self):
    build_history = {
        'm1': {'b1': [(1, self.fail, 1)]},
        'm2': {'b2': [(1, self.good, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testMultipleRevHistory(self):
    build_history = {
        'm1': {'b1': [(1, self.fail, 1), (2, self.good, 2),
                      (3, self.fail, 3), (4, self.good, 4)]},
        'm2': {'b2': [(1, self.fail, 1), (2, self.fail, 2),
                      (3, self.good, 3), (4, self.good, 4)]}}
    revisions = [1, 2, 3, 4]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 4)

  def testMultipleSuccess(self):
    build_history = {
        'm1': {'b1': [(1, self.fail, 1), (2, self.good, 2),
                      (3, self.fail, 3), (4, self.good, 4), (5, self.good, 5)]},
        'm2': {'b2': [(1, self.fail, 1), (2, self.fail, 2),
                      (3, self.good, 3), (4, self.good, 4), (5, self.good, 5)]}}
    revisions = [1, 2, 3, 4, 5]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 5)

  def testMissingFails(self):
    build_history = {
        'm1': {'b1': [(1, self.fail, 1), (2, self.good, 2),
                      (3, self.fail, 3), (5, self.good, 5)]},
        'm2': {'b2': [(1, self.fail, 1), (2, self.fail, 2),
                      (3, self.good, 3), (4, self.good, 4)]}}
    revisions = [1, 2, 3, 4, 5]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testMissingSuccess(self):
    build_history = {
        'm1': {'b1': [(1, self.fail, 1), (2, self.good, 2),
                      (3, self.fail, 3), (5, self.good, 5)]},
        'm2': {'b2': [(1, self.fail, 1), (2, self.fail, 2),
                      (3, self.good, 3), (4, self.good, 4), (6, self.good, 6)]}}
    revisions = [1, 2, 3, 4, 5, 6]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 5)


class CheckLKGRLagTest(unittest.TestCase):
  allowed_lag = 2  # Default allowed lag is 2 hours
  allowed_gap = 150  # Default allowed gap is 150 revisions

  @staticmethod
  def lag(minutes):
    return datetime.timedelta(minutes=minutes)

  def testNoGapSucceeds(self):
    res = lkgr_lib.CheckLKGRLag(self.lag(1), 0,
                                self.allowed_lag, self.allowed_gap)
    self.assertTrue(res)

  def testNoLagSucceeds(self):
    res = lkgr_lib.CheckLKGRLag(self.lag(0), 1,
                                self.allowed_lag, self.allowed_gap)
    self.assertTrue(res)

  def testSimpleSucceeds(self):
    res = lkgr_lib.CheckLKGRLag(self.lag(15), 10,
                                self.allowed_lag, self.allowed_gap)
    self.assertTrue(res)

  def testLagFails(self):
    res = lkgr_lib.CheckLKGRLag(self.lag(60 * 4), 150,
                                self.allowed_lag, self.allowed_gap)
    self.assertFalse(res)

  def testFlexLagSucceeds(self):
    res = lkgr_lib.CheckLKGRLag(self.lag(60 * 4), 10,
                                self.allowed_lag, self.allowed_gap)
    self.assertTrue(res)
