#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Source file for lkgr_lib testcases."""


import datetime
import httplib2
import json
import mock
import os
import sys
import tempfile
import unittest

import google.protobuf.message
from infra.libs.buildbucket.proto import common_pb2
from infra.libs.buildbucket.proto import rpc_pb2
from infra.services.lkgr_finder import lkgr_lib
from infra.services.lkgr_finder.status_generator import StatusGeneratorStub


# TODO(agable): Test everything else once I can import pymox.
class FetchBuildbucketBuildsForBuilderTest(unittest.TestCase):

  @mock.patch('infra.services.lkgr_finder.lkgr_lib._FetchFromBuildbucketImpl')
  def testFetchSucceeded(self, mocked_fetch):
    response_pb = rpc_pb2.SearchBuildsResponse()
    build_pb = response_pb.builds.add()
    build_pb.number = 123
    build_pb.status = common_pb2.SUCCESS
    build_pb.input.gitiles_commit.id = 'a' * 40
    mocked_fetch.return_value = response_pb

    builds = lkgr_lib.FetchBuildbucketBuildsForBuilder(
        'project1/bucket1', 'builder1')
    self.assertEquals(
        builds,
        [lkgr_lib.Build(123, lkgr_lib.STATUS.SUCCESS, 'a' * 40)])

  @mock.patch('infra.services.lkgr_finder.lkgr_lib._FetchFromBuildbucketImpl')
  def testFetchFailed(self, mocked_fetch):
    mocked_fetch.side_effect = httplib2.HttpLib2Error
    builds = lkgr_lib.FetchBuildbucketBuildsForBuilder(
        'project1/bucket1', 'builder1')
    self.assertEquals(builds, None)

  @mock.patch('infra.services.lkgr_finder.lkgr_lib._FetchFromBuildbucketImpl')
  def testProtoError(self, mocked_fetch):
    mocked_fetch.side_effect = google.protobuf.message.DecodeError
    builds = lkgr_lib.FetchBuildbucketBuildsForBuilder(
        'project1/bucket1', 'builder1')
    self.assertEquals(builds, None)

  @mock.patch('infra.services.lkgr_finder.lkgr_lib._FetchFromBuildbucketImpl')
  def testMalformattedBucket(self, mocked_fetch):
    builds = lkgr_lib.FetchBuildbucketBuildsForBuilder(
        'project1_bucket1', 'builder1')
    self.assertEquals(builds, None)
    mocked_fetch.assert_not_called()

  @mock.patch('infra.services.lkgr_finder.lkgr_lib._FetchFromBuildbucketImpl')
  def testFetchBuildCanceled(self, mocked_fetch):
    response_pb = rpc_pb2.SearchBuildsResponse()
    build_pb = response_pb.builds.add()
    build_pb.number = 123
    build_pb.status = common_pb2.CANCELED
    build_pb.input.gitiles_commit.id = 'a' * 40
    mocked_fetch.return_value = response_pb

    builds = lkgr_lib.FetchBuildbucketBuildsForBuilder(
        'project1/bucket1', 'builder1')
    self.assertEquals(
        builds,
        [lkgr_lib.Build(123, lkgr_lib.STATUS.UNKNOWN, 'a' * 40)])

  @mock.patch('infra.services.lkgr_finder.lkgr_lib._FetchFromBuildbucketImpl')
  def testFetchBuildFailed(self, mocked_fetch):
    response_pb = rpc_pb2.SearchBuildsResponse()
    build_pb = response_pb.builds.add()
    build_pb.number = 123
    build_pb.status = common_pb2.FAILURE
    build_pb.input.gitiles_commit.id = 'a' * 40
    mocked_fetch.return_value = response_pb

    builds = lkgr_lib.FetchBuildbucketBuildsForBuilder(
        'project1/bucket1', 'builder1')
    self.assertEquals(
        builds,
        [lkgr_lib.Build(123, lkgr_lib.STATUS.FAILURE, 'a' * 40)])

  @mock.patch('infra.services.lkgr_finder.lkgr_lib._FetchFromBuildbucketImpl')
  def testFetchMissingPieces(self, mocked_fetch):
    response_pb = rpc_pb2.SearchBuildsResponse()
    build_pb = response_pb.builds.add()
    build_pb.number = 123
    build_pb.status = common_pb2.SCHEDULED
    mocked_fetch.return_value = response_pb

    builds = lkgr_lib.FetchBuildbucketBuildsForBuilder(
        'project1/bucket1', 'builder1')
    self.assertEquals(builds, [])


class CollateRevisionHistoryTest(unittest.TestCase):

  def testSortsBuildHistories(self):
    build_history = {
      'master1': {
        'builder1': [
          lkgr_lib.Build(121, lkgr_lib.STATUS.SUCCESS,
                         'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab'),
          lkgr_lib.Build(123, lkgr_lib.STATUS.SUCCESS,
                         'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
          lkgr_lib.Build(122, lkgr_lib.STATUS.SUCCESS,
                         'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac'),
        ]
      }
    }

    expected_builds = [
      lkgr_lib.Build(123, lkgr_lib.STATUS.SUCCESS,
                     'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
      lkgr_lib.Build(121, lkgr_lib.STATUS.SUCCESS,
                     'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab'),
      lkgr_lib.Build(122, lkgr_lib.STATUS.SUCCESS,
                     'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac'),
    ]

    repo = mock.MagicMock()
    def mock_repo_sort(history, keyfunc=None):
      return sorted(history, key=keyfunc)
    repo.sort = mock.MagicMock(side_effect=mock_repo_sort)

    collated_build_history, _ = lkgr_lib.CollateRevisionHistory(
        build_history, repo)

    actual_builds = (
        collated_build_history.get('master1', {}).get('builder1', []))
    self.assertEquals(actual_builds, expected_builds)

  def testSortsRevisions(self):
    build_history = {
      'master1': {
        'builder1': [
          lkgr_lib.Build(121, lkgr_lib.STATUS.SUCCESS,
                         'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab'),
          lkgr_lib.Build(123, lkgr_lib.STATUS.SUCCESS,
                         'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
          lkgr_lib.Build(122, lkgr_lib.STATUS.SUCCESS,
                         'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac'),
        ]
      }
    }

    expected_revisions = [
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab',
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac',
    ]

    repo = mock.MagicMock()
    def mock_repo_sort(history, keyfunc=None):
      return sorted(history, key=keyfunc)
    repo.sort = mock.MagicMock(side_effect=mock_repo_sort)

    _, actual_revisions = lkgr_lib.CollateRevisionHistory(
        build_history, repo)

    self.assertEquals(actual_revisions, expected_revisions)


class FindLKGRCandidateTest(unittest.TestCase):

  def setUp(self):
    self.status_stub = StatusGeneratorStub()
    self.good = lkgr_lib.STATUS.SUCCESS
    self.fail = lkgr_lib.STATUS.FAILURE
    self.keyfunc = int

  def testSimpleSucceeds(self):
    build_history = {'m1': {'b1': [lkgr_lib.Build(1, self.good, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 1)

  def testSimpleFails(self):
    build_history = {'m1': {'b1': [lkgr_lib.Build(1, self.fail, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testModerateSuccess(self):
    build_history = {
        'm1': {'b1': [lkgr_lib.Build(1, self.good, 1)]},
        'm2': {'b2': [lkgr_lib.Build(1, self.good, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 1)

  def testModerateFailsOne(self):
    build_history = {
        'm1': {'b1': [lkgr_lib.Build(1, self.good, 1)]},
        'm2': {'b2': [lkgr_lib.Build(1, self.fail, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testModerateFailsTwo(self):
    build_history = {
        'm1': {'b1': [lkgr_lib.Build(1, self.fail, 1)]},
        'm2': {'b2': [lkgr_lib.Build(1, self.good, 1)]}}
    revisions = [1]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testMultipleRevHistory(self):
    build_history = {
        'm1': {'b1': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.good, 2),
                      lkgr_lib.Build(3, self.fail, 3),
                      lkgr_lib.Build(4, self.good, 4)]},
        'm2': {'b2': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.fail, 2),
                      lkgr_lib.Build(3, self.good, 3),
                      lkgr_lib.Build(4, self.good, 4)]}}
    revisions = [1, 2, 3, 4]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 4)

  def testMultipleSuccess(self):
    build_history = {
        'm1': {'b1': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.good, 2),
                      lkgr_lib.Build(3, self.fail, 3),
                      lkgr_lib.Build(4, self.good, 4),
                      lkgr_lib.Build(5, self.good, 5)]},
        'm2': {'b2': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.fail, 2),
                      lkgr_lib.Build(3, self.good, 3),
                      lkgr_lib.Build(4, self.good, 4),
                      lkgr_lib.Build(5, self.good, 5)]}}
    revisions = [1, 2, 3, 4, 5]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 5)

  def testMissingFails(self):
    build_history = {
        'm1': {'b1': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.good, 2),
                      lkgr_lib.Build(3, self.fail, 3),
                      lkgr_lib.Build(5, self.good, 5)]},
        'm2': {'b2': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.fail, 2),
                      lkgr_lib.Build(3, self.good, 3),
                      lkgr_lib.Build(4, self.good, 4)]}}
    revisions = [1, 2, 3, 4, 5]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, None)

  def testMissingSuccess(self):
    build_history = {
        'm1': {'b1': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.good, 2),
                      lkgr_lib.Build(3, self.fail, 3),
                      lkgr_lib.Build(5, self.good, 5)]},
        'm2': {'b2': [lkgr_lib.Build(1, self.fail, 1),
                      lkgr_lib.Build(2, self.fail, 2),
                      lkgr_lib.Build(3, self.good, 3),
                      lkgr_lib.Build(4, self.good, 4),
                      lkgr_lib.Build(6, self.good, 6)]}}
    revisions = [1, 2, 3, 4, 5, 6]
    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, self.keyfunc, self.status_stub)
    self.assertEquals(candidate, 5)

  def testNoBuilderHistory(self):
    build_history = {
        'm1': {'b1': []},
    }
    revisions = [1]

    def allow_norev_keyfunc(val):
      if val is lkgr_lib.NOREV:
        return -1
      return int(val)

    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, allow_norev_keyfunc, self.status_stub)
    self.assertEquals(candidate, None)


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


class LoadBuildsTest(unittest.TestCase):

  def testSuccess(self):
    try:
      f = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
      with f:
        f.write(json.dumps({
          'builds': {
            'master1': {
              'builder1': [
                [123, lkgr_lib.STATUS.SUCCESS, '01234567']
              ]
            },
          },
          'version': lkgr_lib._BUILD_DATA_VERSION,
        }))

      expected_builds = {
        'master1': {
          'builder1': [
            lkgr_lib.Build(123, lkgr_lib.STATUS.SUCCESS, '01234567'),
          ]
        }
      }
      actual_builds = lkgr_lib.LoadBuilds(f.name)
      self.assertEquals(actual_builds, expected_builds)
    finally:
      if os.path.exists(f.name):  # pragma: no branch
        os.unlink(f.name)

  def testOldVersion(self):
    try:
      f = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
      with f:
        f.write(json.dumps({
          'builds': {
            'master1': {
              'builder1': [
                [123, lkgr_lib.STATUS.SUCCESS, '01234567']
              ]
            },
          },
          'version': lkgr_lib._BUILD_DATA_VERSION - 1,
        }))

      expected_builds = None
      actual_builds = lkgr_lib.LoadBuilds(f.name)
      self.assertEquals(actual_builds, expected_builds)
    finally:
      if os.path.exists(f.name):  # pragma: no branch
        os.unlink(f.name)

  def testNoVersion(self):
    try:
      f = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
      with f:
        f.write(json.dumps({
          'master1': {
            'builder1': [
              [123, lkgr_lib.STATUS.SUCCESS, '01234567']
            ]
          },
        }))

      expected_builds = None
      actual_builds = lkgr_lib.LoadBuilds(f.name)
      self.assertEquals(actual_builds, expected_builds)
    finally:
      if os.path.exists(f.name):  # pragma: no branch
        os.unlink(f.name)


class DumpBuildsTest(unittest.TestCase):

  def testSuccess(self):
    try:
      f = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
      builds = {
        'master1': {
          'builder1': [
            lkgr_lib.Build(123, lkgr_lib.STATUS.SUCCESS, '01234567'),
          ]
        }
      }

      expected_contents = {
        'builds': {
          'master1': {
            'builder1': [
              [123, lkgr_lib.STATUS.SUCCESS, '01234567'],
            ]
          }
        },
        'version': lkgr_lib._BUILD_DATA_VERSION,
      }
      lkgr_lib.DumpBuilds(builds, f.name)
      with f:
        actual_contents = json.load(f)
      self.assertEquals(actual_contents, expected_contents)
    finally:
      if os.path.exists(f.name):  # pragma: no branch
        os.unlink(f.name)
