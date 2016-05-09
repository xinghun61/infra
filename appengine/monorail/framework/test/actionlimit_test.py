# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for actionlimit module."""

import time
import unittest

from framework import actionlimit
from proto import user_pb2


class ActionLimitTest(unittest.TestCase):

  def testNeedCaptchaNoUser(self):
    action = actionlimit.ISSUE_COMMENT
    self.assertFalse(actionlimit.NeedCaptcha(None, action))

  def testNeedCaptchaAuthUserNoPreviousActions(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    self.assertFalse(actionlimit.NeedCaptcha(user, action))

  def testNeedCaptchaAuthUserLifetimeExcessiveActivityException(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    life_max = actionlimit.ACTION_LIMITS[action][3]

    for _i in range(0, life_max):
      actionlimit.CountAction(user, action)

    self.assertRaises(
        actionlimit.ExcessiveActivityException,
        actionlimit.NeedCaptcha, user, action)

  def testNeedCaptchaAuthUserLifetimeIgnoresTimeout(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    (period, _soft_limit, _hard_limit,
     life_max) = actionlimit.ACTION_LIMITS[action]
    now = int(time.time())
    later = now + period + 1  # a future in which our timestamp is expired

    for _i in range(0, life_max):
      actionlimit.CountAction(user, action, now=now)

    self.assertRaises(
        actionlimit.ExcessiveActivityException,
        actionlimit.NeedCaptcha, user, action, now=later)

  # TODO(jrobbins): write a soft limit captcha test.

  def testNeedCaptchaAuthUserHardLimitExcessiveActivityException(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    (_period, _soft_limit, hard_limit,
     _life_max) = actionlimit.ACTION_LIMITS[action]

    for _i in range(0, hard_limit):
      actionlimit.CountAction(user, action)

    self.assertRaises(
        actionlimit.ExcessiveActivityException,
        actionlimit.NeedCaptcha, user, action)

  def testNeedCaptchaAuthUserHardLimitRespectsTimeout(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    (period, _soft_limit, hard_limit,
     _life_max) = actionlimit.ACTION_LIMITS[action]
    now = int(time.time())
    later = now + period + 1  # a future in which our timestamp is expired

    for _i in range(0, hard_limit):
      actionlimit.CountAction(user, action, now=now)

    # if we didn't pass later, we'd get an exception
    self.assertFalse(actionlimit.NeedCaptcha(user, action, now=later))

  def testNeedCaptchaNoLifetimeLimit(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    life_max = actionlimit.ACTION_LIMITS[action][3]
    actionlimit.GetLimitPB(user, action).lifetime_count = life_max + 1

    self.assertRaises(
        actionlimit.ExcessiveActivityException,
        actionlimit.NeedCaptcha, user, action, skip_lifetime_check=False)
    self.assertFalse(
        actionlimit.NeedCaptcha(user, action, skip_lifetime_check=True))

  def testCountActionResetRecentActions(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    limit = actionlimit.GetLimitPB(user, action)
    limit.recent_count = 10
    limit.reset_timestamp = 11

    limit = actionlimit.GetLimitPB(user, action)
    self.assertEqual(10, limit.recent_count)
    self.assertEqual(11, limit.reset_timestamp)

    actionlimit.ResetRecentActions(user, action)

    limit = actionlimit.GetLimitPB(user, action)
    self.assertEqual(0, limit.recent_count)
    self.assertEqual(0, limit.reset_timestamp)

  def testCountActionIncrementsRecentCount(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    (_period, soft_limit, _hard_limit,
     _life_max) = actionlimit.ACTION_LIMITS[action]

    for i in range(1, soft_limit):
      actionlimit.CountAction(user, action)
      limit = actionlimit.GetLimitPB(user, action)
      self.assertEqual(i, limit.recent_count)
      self.assertEqual(i, limit.lifetime_count)

  def testCountActionPeriodExpiration(self):
    action = actionlimit.ISSUE_COMMENT
    user = user_pb2.User()
    (period, soft_limit, _hard_limit,
     _life_max) = actionlimit.ACTION_LIMITS[action]
    now = int(time.time())
    later = now + period + 1  # a future in which our timestamp is expired

    for i in range(1, soft_limit):
      actionlimit.CountAction(user, action, now=now)
      limit = actionlimit.GetLimitPB(user, action)
      self.assertEqual(i, limit.recent_count)
      self.assertEqual(i, limit.lifetime_count)

    actionlimit.CountAction(user, action, now=now)
    self.assertEqual(soft_limit, limit.recent_count)
    self.assertEqual(soft_limit, limit.lifetime_count)

    actionlimit.CountAction(user, action, now=later)
    self.assertEqual(1, limit.recent_count)
    self.assertEqual(soft_limit + 1, limit.lifetime_count)

  def testCustomizeLifetimeLimit(self):
    user = user_pb2.User()

    self.assertIsNone(user.get_assigned_value('issue_comment_limit'))
    actionlimit.CustomizeLimit(user, actionlimit.ISSUE_COMMENT, 10, 100, 500)
    self.assertIsNotNone(user.get_assigned_value('issue_comment_limit'))
    limit = user.issue_comment_limit

    # sets the specified limit
    self.assertIsNotNone(limit.get_assigned_value('lifetime_limit'))
    self.assertEqual(500, limit.lifetime_limit)
    self.assertEqual(10, limit.period_soft_limit)
    self.assertEqual(100, limit.period_hard_limit)

    # sets initial values to zero
    self.assertEqual(0, limit.recent_count)
    self.assertEqual(0, limit.reset_timestamp)
