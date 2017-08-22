# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock

from google.appengine.ext import ndb

import webapp2

from gae_libs.testcase import TestCase
from handlers import collect_tree_closures
from model.tree_closure import TreeClosure
from model.tree_closure import TreeStatus


class CollectTreeClosuresTest(TestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/collect-tree-closures', collect_tree_closures.CollectTreeClosures),
      ],
      debug=True)

  def testGetCurrentCheckingPointForTreeWithoutExistingData(self):
    self.MockUTCNow(datetime(2017, 04, 13, 10, 10, 10))
    expected_checking_point = datetime(2017, 01, 13, 10, 10, 10)
    checking_point = collect_tree_closures._GetCurrentCheckingPointForTree('c')
    self.assertEqual(expected_checking_point, checking_point)

  def testGetCurrentCheckingPointForTreeWithExistingData(self):
    TreeClosure(tree_name='c', closed_time=datetime(2017, 04, 10, 10, 10)).put()
    TreeClosure(
        tree_name='c',
        closed_time=datetime(2017, 04, 11, 05, 05),
        opened_time=datetime(2017, 04, 11, 05, 15)).put()
    expected_checking_point = datetime(2017, 04, 11, 05, 15)
    checking_point = collect_tree_closures._GetCurrentCheckingPointForTree('c')
    self.assertEqual(expected_checking_point, checking_point)

  @mock.patch.object(collect_tree_closures.HttpClientAppengine, 'Get')
  def testRetrieveTreeStatusSuccess(self, mocked_Get):
    mocked_Get.side_effect = [(200, json.dumps([{
        'date': '2017-04-01 12:12:12',
        'message': 'm1',
        'general_state': 'open',
        'username': 'test@chromium.org',
    }, {
        'date': '2017-04-01 12:12:12',
        'message': 'm1',
        'general_state': 'open',
        'username': 'test@chromium.org',
    }]))]
    statuses = collect_tree_closures._RetrieveTreeStatus(
        'chromium', datetime(2017, 03, 31))
    self.assertEqual(1, len(statuses))
    self.assertEqual(statuses[0].time, datetime(2017, 04, 01, 12, 12, 12))
    self.assertEqual(statuses[0].message, 'm1')
    self.assertEqual(statuses[0].state, 'open')
    self.assertEqual(statuses[0].username, 'test@chromium.org')

    mocked_Get.assert_called_once_with(
        'https://chromium-status.appspot.com/allstatus',
        params={
            'limit': 1000,
            'format': 'json',
            'endTime': 1490918400,
        })

  @mock.patch.object(collect_tree_closures.HttpClientAppengine, 'Get')
  def testRetrieveTreeStatusFailure(self, mocked_Get):
    mocked_Get.side_effect = [(400, 'error')]
    statuses = collect_tree_closures._RetrieveTreeStatus(
        'chromium', datetime(2017, 03, 31), end_time=datetime(2017, 04, 01))

    self.assertEqual(0, len(statuses))
    mocked_Get.assert_called_once_with(
        'https://chromium-status.appspot.com/allstatus',
        params={
            'limit': 1000,
            'format': 'json',
            'endTime': 1490918400,
            'startTime': 1491004800,
        })

  def testExtractFailureInfoWithFullBuildLink(self):
    message = ('Tree is closed (Automatic: "compile" on '
               'http://build.chromium.org/p/m/builders/b/builds/1 "b" from ...')
    info = collect_tree_closures._ExtractFailureInfo(message)
    self.assertEqual(('m', 'b', '1', 'compile'), info)

  def testExtractFailureInfoWithPartialBuildLink(self):
    message = ('Tree is closed (Automatic: "compile" on '
               '/builders/b/builds/1 "b" from ...')
    info = collect_tree_closures._ExtractFailureInfo(message)
    self.assertEqual((None, 'b', '1', 'compile'), info)

  def testExtractFailureInfoWithUnknownMessageFormat(self):
    message = 'Tree is closed for blink rename'
    info = collect_tree_closures._ExtractFailureInfo(message)
    self.assertEqual((None, None, None, None), info)

  def testDetectTreeClosureForTreeWithOneCompleteClosure(self):
    all_statuses = [
        TreeStatus(state='open'),
        # A complete closure.
        TreeStatus(
            time=datetime(2017, 03, 31, 0, 0, 0),  # timestamp is 1490918400.
            message=('Tree is closed (Automatic: "compile" on '
                     '/builders/Win%20x64/builds/10327 "Win x64" from blabla'),
            state='closed',
            username='buildbot@chromium.org',),
        TreeStatus(
            time=datetime(2017, 03, 31, 0, 1, 0),
            message='Tree is closed (sheriff investigating)',
            state='closed',
            username='test@chromium.org',),
        TreeStatus(
            time=datetime(2017, 03, 31, 0, 5, 0),
            message='possible flake',
            state='open',
            username='test@chromium.org',),
        TreeStatus(
            time=datetime(2017, 03, 31, 0, 15, 0),
            message='speculative Reverted r12345678',
            state='open',
            username='test@chromium.org',),
        # An incomplete closure.
        TreeStatus(state='closed')
    ]
    num = collect_tree_closures._DetectTreeClosureForTree('c', all_statuses)
    self.assertEqual(1, num)

    key_str_id = '%s-%s' % ('c', 1490918400)
    closure = ndb.Key(TreeClosure, key_str_id).get()
    self.assertIsNotNone(closure)
    self.assertEqual('c', closure.tree_name)
    self.assertEqual(all_statuses[1:-1], closure.statuses)
    self.assertEqual(datetime(2017, 03, 31, 0, 0, 0), closure.closed_time)
    self.assertEqual(datetime(2017, 03, 31, 0, 5, 0), closure.opened_time)
    self.assertEqual(
        datetime(2017, 03, 31, 0, 15, 0), closure.latest_action_time)
    self.assertTrue(closure.auto_closed)
    self.assertFalse(closure.auto_opened)
    self.assertTrue(closure.possible_flake)
    self.assertTrue(closure.has_revert)
    self.assertIsNone(closure.master_name)
    self.assertEqual('Win x64', closure.builder_name)
    self.assertEqual('10327', closure.build_id)
    self.assertEqual('compile', closure.step_name)

  def testDetectTreeClosureForTreeWithIncompleteClosure(self):
    all_statuses = [
        # A incomplete closure.
        TreeStatus(
            time=datetime(2017, 03, 31, 0, 0, 0),  # timestamp is 1490918400.
            message=('Tree is closed (Automatic: "compile" on '
                     '/builders/Win%20x64/builds/10327 "Win x64" from blabla'),
            state='closed',
            username='buildbot@chromium.org',),
        TreeStatus(
            time=datetime(2017, 03, 31, 0, 15, 0),
            message='possible flake',
            state='open',
            username='test@chromium.org',),
    ]
    num = collect_tree_closures._DetectTreeClosureForTree('c', all_statuses)
    self.assertEqual(0, num)

    key_str_id = '%s-%s' % ('c', 1490918400)
    closure = ndb.Key(TreeClosure, key_str_id).get()
    self.assertIsNone(closure)

  @mock.patch.object(
      collect_tree_closures,
      '_GetCurrentCheckingPointForTree',
      return_value=datetime(2017, 03, 01))
  @mock.patch.object(
      collect_tree_closures, '_RetrieveTreeStatus', return_value=['a'])
  @mock.patch.object(
      collect_tree_closures, '_DetectTreeClosureForTree', return_value=2)
  def testGetWithStartTimeAndEndTime(self, mocked_detect_fun,
                                     mocked_retrive_fun, mocked_check_fun):
    response = self.test_app.get(
        '/collect-tree-closures',
        params={'start_time': '2017-04-01',
                'end_time': '2017-04-05'},
        headers={'X-AppEngine-Cron': 'true'})
    self.assertEquals(200, response.status_int)
    expected_result = {'chromium': 2}
    self.assertEqual(expected_result, response.json_body)
    mocked_check_fun.assert_not_called()
    mocked_retrive_fun.assert_called_once_with(
        'chromium', datetime(2017, 04, 01), end_time=datetime(2017, 04, 05))
    mocked_detect_fun.assert_called_once_with('chromium', ['a'])

  @mock.patch.object(
      collect_tree_closures,
      '_GetCurrentCheckingPointForTree',
      return_value=datetime(2017, 04, 01))
  @mock.patch.object(
      collect_tree_closures, '_RetrieveTreeStatus', return_value=['a'])
  @mock.patch.object(
      collect_tree_closures, '_DetectTreeClosureForTree', return_value=2)
  def testGetWithoutStartTime(self, mocked_detect_fun, mocked_retrive_fun,
                              mocked_check_fun):
    response = self.test_app.get('/collect-tree-closures',
                                 headers={'X-AppEngine-Cron': 'true'})
    self.assertEquals(200, response.status_int)
    expected_result = {'chromium': 2}
    self.assertEqual(expected_result, response.json_body)
    mocked_check_fun.assert_called_once_with('chromium')
    mocked_retrive_fun.assert_called_once_with(
        'chromium', datetime(2017, 04, 01), end_time=None)
    mocked_detect_fun.assert_called_once_with('chromium', ['a'])
