# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs import email_util

class EmailUtilTest(unittest.TestCase):

  def testObscureEmails(self):
    emails = ['id', 'test@google.com',
              'chromium-try-flakes@appspot.gserviceaccount.com']
    domains = 'google.com'
    expected_emails = ['xx', 'xxxx@google.com',
                       'chromium-try-flakes@appspot.gserviceaccount.com']
    self.assertEqual(expected_emails, email_util.ObscureEmails(emails, domains))
