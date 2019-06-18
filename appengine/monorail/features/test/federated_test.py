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
from framework.exceptions import InvalidExternalIssueReference


# Schema: tracker, shortlink.
VALID_SHORTLINKS = [
    ('google', 'b/1'),
    ('google', 'b/123456'),
    ('google', 'b/1234567890123')]


# Schema: tracker, shortlink.
INVALID_SHORTLINKS = [
   ('google', 'b'),
   ('google', 'b/'),
   ('google', 'b//123'),
   ('google', 'b/123/123')]


class FederatedTest(unittest.TestCase):
  """Test public module methods."""

  def testIsShortlinkValid_Valid(self):
    for _, shortlink in VALID_SHORTLINKS:
      self.assertTrue(federated.IsShortlinkValid(shortlink),
        'Expected %s to be a valid shortlink for any tracker.'
        % shortlink)

  def testIsShortlinkValid_Invalid(self):
    for _, shortlink in INVALID_SHORTLINKS:
      self.assertFalse(federated.IsShortlinkValid(shortlink),
        'Expected %s to be an invalid shortlink for any tracker.'
        % shortlink)

  def testFromShortlink_Valid(self):
    for _, shortlink in VALID_SHORTLINKS:
      issue = federated.FromShortlink(shortlink)
      self.assertEqual(shortlink, issue.shortlink, (
          'Expected %s to be converted into a valid tracker object '
          'with shortlink %s' % (shortlink, issue.shortlink)))

  def testFromShortlink_Invalid(self):
    for _, shortlink in INVALID_SHORTLINKS:
      self.assertIsNone(federated.FromShortlink(shortlink))


class FederatedIssueTest(unittest.TestCase):

  def testInit_NotImplemented(self):
    """By default, __init__ raises NotImplementedError.

    Because __init__ calls IsShortlinkValid. See test below.
    """
    with self.assertRaises(NotImplementedError):
      federated.FederatedIssue('a')

  def testIsShortlinkValid_NotImplemented(self):
    """By default, IsShortlinkValid raises NotImplementedError."""
    with self.assertRaises(NotImplementedError):
      federated.FederatedIssue('a').IsShortlinkValid('rutabaga')


class GoogleIssueTrackerIssueTest(unittest.TestCase):

  def setUp(self):
    self.valid_shortlinks = [s for tracker, s in VALID_SHORTLINKS
      if tracker == 'google']
    self.invalid_shortlinks = [s for tracker, s in INVALID_SHORTLINKS
      if tracker == 'google']

  def testInit_ValidatesValidShortlink(self):
    for shortlink in self.valid_shortlinks:
      issue = federated.GoogleIssueTrackerIssue(shortlink)
      self.assertEqual(issue.shortlink, shortlink)

  def testInit_ValidatesInvalidShortlink(self):
    for shortlink in self.invalid_shortlinks:
      with self.assertRaises(InvalidExternalIssueReference):
        federated.GoogleIssueTrackerIssue(shortlink)

  def testIsShortlinkValid_Valid(self):
    for shortlink in self.valid_shortlinks:
      self.assertTrue(
        federated.GoogleIssueTrackerIssue.IsShortlinkValid(shortlink),
        'Expected %s to be a valid shortlink for Google.'
        % shortlink)

  def testIsShortlinkValid_Invalid(self):
    for shortlink in self.invalid_shortlinks:
      self.assertFalse(
        federated.GoogleIssueTrackerIssue.IsShortlinkValid(shortlink),
        'Expected %s to be an invalid shortlink for Google.'
        % shortlink)

  def testToURL(self):
    self.assertEqual('https://issuetracker.google.com/issues/123456',
        federated.GoogleIssueTrackerIssue('b/123456').ToURL())

  def testSummary(self):
    self.assertEqual('Google Issue Tracker issue 123456.',
        federated.GoogleIssueTrackerIssue('b/123456').Summary())
