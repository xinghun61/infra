# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for monorail.feature.federated."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from features import federated


class FederatedTest(unittest.TestCase):
  """Test public module methods."""

  def testShortlinkIsValid_Google(self):
   self.assertTrue(federated.shortlink_is_valid('b/1'))
   self.assertTrue(federated.shortlink_is_valid('b/123456'))
   self.assertTrue(federated.shortlink_is_valid('b/1234567890123'))
   self.assertFalse(federated.shortlink_is_valid('b'))
   self.assertFalse(federated.shortlink_is_valid('b/'))
   self.assertFalse(federated.shortlink_is_valid('b//123'))
   self.assertFalse(federated.shortlink_is_valid('b/123/123'))


class FederatedTrackerBaseTest(unittest.TestCase):

  def setUp(self):
    self.federatedTracker = federated.FederatedTrackerBase()

  def testIsShortlinkValid_NotImplemented(self):
    """By default, IsShortlinkValid raises NotImplementedError."""
    with self.assertRaises(NotImplementedError):
     self.federatedTracker.IsShortlinkValid('rutabaga')


class GoogleIssueTrackerTest(unittest.TestCase):

  def setUp(self):
    self.federatedTracker = federated.GoogleIssueTracker()

  def testIsShortlinkValid_Valid(self):
    """IsShortlinkValid returns True for valid shortlinks."""
    self.assertTrue(self.federatedTracker.IsShortlinkValid('b/1'))
    self.assertTrue(self.federatedTracker.IsShortlinkValid('b/123456'))
    self.assertTrue(self.federatedTracker.IsShortlinkValid('b/1234567890123'))

  def testIsShortlinkValid_Invalid(self):
    """IsShortlinkValid returns False for invalid shortlinks."""
    self.assertFalse(self.federatedTracker.IsShortlinkValid('b'))
    self.assertFalse(self.federatedTracker.IsShortlinkValid('b/'))
    self.assertFalse(self.federatedTracker.IsShortlinkValid('b//123'))
    self.assertFalse(self.federatedTracker.IsShortlinkValid('b/123/123'))
