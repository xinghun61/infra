#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Source file for lkgr_lib testcases."""


import datetime
import os
import sys
import unittest

from infra.services.lkgr_finder import lkgr_lib
from infra.services.lkgr_finder.status_generator import StatusGeneratorStub


# TODO(agable): Test everything else once I can import pymox.


class FindLKGRCandidateTest(unittest.TestCase):
  status_stub = StatusGeneratorStub()
  good = lkgr_lib.STATUS.SUCCESS
  fail = lkgr_lib.STATUS.FAILURE
  keyfunc = lkgr_lib.SvnWrapper(None, None).keyfunc

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


class SvnWrapperTest(unittest.TestCase):
  url = 'svn://my.svn.server/repo/trunk'

  # TODO(agable): Test get_lag once I can import pymox

  def testCheckRevSucceeds(self):
    s = lkgr_lib.SvnWrapper(self.url, None)
    res = s.check_rev(12345)
    self.assertTrue(res)

  def testCheckRevStringSucceeds(self):
    s = lkgr_lib.SvnWrapper(self.url, None)
    res = s.check_rev('12345')
    self.assertTrue(res)

  def testCheckRevFails(self):
    s = lkgr_lib.SvnWrapper(self.url, None)
    res = s.check_rev('deadbeef')
    self.assertFalse(res)

  def testCheckRevNOREVFails(self):
    s = lkgr_lib.SvnWrapper(self.url, None)
    res = s.check_rev(lkgr_lib.NOREV)
    self.assertFalse(res)

  def testKeyfuncSucceeds(self):
    s = lkgr_lib.SvnWrapper(self.url, None)
    res = s.keyfunc(12345)
    self.assertEquals(res, 12345)

  def testKeyfuncFails(self):
    s = lkgr_lib.SvnWrapper(self.url, None)
    res = s.keyfunc('deadbeef')
    self.assertEquals(res, None)

  def testSort(self):
    s = lkgr_lib.SvnWrapper(self.url, None)
    revs = [(4567, 'foo'), (2345, 'bar'), (6789, 'baz')]
    res = s.sort(revs, keyfunc=lambda x: x[0])
    self.assertEquals(res, [(2345, 'bar'), (4567, 'foo'), (6789, 'baz')])
