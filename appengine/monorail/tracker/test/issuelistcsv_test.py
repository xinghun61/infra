# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issuelistcsv module."""

import unittest

from framework import permissions
from services import service_manager
from testing import testing_helpers
from tracker import issuelistcsv


class IssueListCSVTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services()
    self.servlet = issuelistcsv.IssueListCsv(
        'req', 'res', services=self.services)

  def testGatherPageData_AnonUsers(self):
    """Anonymous users cannot download the issue list."""
    mr = testing_helpers.MakeMonorailRequest()
    mr.auth.user_id = 0
    self.assertRaises(permissions.PermissionException,
                      self.servlet.GatherPageData, mr)


class IssueListCSVFunctionsTest(unittest.TestCase):

  def testRewriteColspec(self):
    self.assertEqual('', issuelistcsv._RewriteColspec(''))

    self.assertEqual('a B c', issuelistcsv._RewriteColspec('a B c'))

    self.assertEqual('a Summary AllLabels B Opened OpenedTimestamp c',
                     issuelistcsv._RewriteColspec('a summary B opened c'))

    self.assertEqual('Closed ClosedTimestamp Modified ModifiedTimestamp',
                     issuelistcsv._RewriteColspec('Closed Modified'))

    self.assertEqual('OwnerModified OwnerModifiedTimestamp',
                     issuelistcsv._RewriteColspec('OwnerModified'))

  def testEscapeCSV(self):
    self.assertEqual('', issuelistcsv.EscapeCSV(None))
    self.assertEqual(0, issuelistcsv.EscapeCSV(0))
    self.assertEqual('', issuelistcsv.EscapeCSV(''))
    self.assertEqual('hello', issuelistcsv.EscapeCSV('hello'))
    self.assertEqual('hello', issuelistcsv.EscapeCSV('  hello '))

    # Double quotes are escaped as two double quotes.
    self.assertEqual("say 'hello'", issuelistcsv.EscapeCSV("say 'hello'"))
    self.assertEqual('say ""hello""', issuelistcsv.EscapeCSV('say "hello"'))

    # Things that look like formulas are prefixed with a single quote because
    # some formula functions can have side-effects.  See:
    # https://www.contextis.com/resources/blog/comma-separated-vulnerabilities/
    self.assertEqual("'=2+2", issuelistcsv.EscapeCSV('=2+2'))
    self.assertEqual("'=CMD| del *.*", issuelistcsv.EscapeCSV('=CMD| del *.*'))

    # Some spreadsheets apparently allow formula cells that start with
    # plus, minus, and at-signs.
    self.assertEqual("'+2+2", issuelistcsv.EscapeCSV('+2+2'))
    self.assertEqual("'-2+2", issuelistcsv.EscapeCSV('-2+2'))
    self.assertEqual("'@2+2", issuelistcsv.EscapeCSV('@2+2'))

    self.assertEqual(
      u'division\xc3\xb7sign',
      issuelistcsv.EscapeCSV(u'division\xc3\xb7sign'))
