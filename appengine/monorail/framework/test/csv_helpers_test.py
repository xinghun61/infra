# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for csv_helpers functions."""

import unittest

from framework import csv_helpers


class IssueListCSVFunctionsTest(unittest.TestCase):

  def testRewriteColspec(self):
    self.assertEqual('', csv_helpers.RewriteColspec(''))

    self.assertEqual('a B c', csv_helpers.RewriteColspec('a B c'))

    self.assertEqual('a Summary AllLabels B Opened OpenedTimestamp c',
                     csv_helpers.RewriteColspec('a summary B opened c'))

    self.assertEqual('Closed ClosedTimestamp Modified ModifiedTimestamp',
                     csv_helpers.RewriteColspec('Closed Modified'))

    self.assertEqual('OwnerModified OwnerModifiedTimestamp',
                     csv_helpers.RewriteColspec('OwnerModified'))

  def testReformatRowsForCSV(self):
    # TODO(jojwang): write this test
    pass

  def testEscapeCSV(self):
    self.assertEqual('', csv_helpers.EscapeCSV(None))
    self.assertEqual(0, csv_helpers.EscapeCSV(0))
    self.assertEqual('', csv_helpers.EscapeCSV(''))
    self.assertEqual('hello', csv_helpers.EscapeCSV('hello'))
    self.assertEqual('hello', csv_helpers.EscapeCSV('  hello '))

    # Double quotes are escaped as two double quotes.
    self.assertEqual("say 'hello'", csv_helpers.EscapeCSV("say 'hello'"))
    self.assertEqual('say ""hello""', csv_helpers.EscapeCSV('say "hello"'))

    # Things that look like formulas are prefixed with a single quote because
    # some formula functions can have side-effects.  See:
    # https://www.contextis.com/resources/blog/comma-separated-vulnerabilities/
    self.assertEqual("'=2+2", csv_helpers.EscapeCSV('=2+2'))
    self.assertEqual("'=CMD| del *.*", csv_helpers.EscapeCSV('=CMD| del *.*'))

    # Some spreadsheets apparently allow formula cells that start with
    # plus, minus, and at-signs.
    self.assertEqual("'+2+2", csv_helpers.EscapeCSV('+2+2'))
    self.assertEqual("'-2+2", csv_helpers.EscapeCSV('-2+2'))
    self.assertEqual("'@2+2", csv_helpers.EscapeCSV('@2+2'))

    self.assertEqual(
      u'division\xc3\xb7sign',
      csv_helpers.EscapeCSV(u'division\xc3\xb7sign'))
