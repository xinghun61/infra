#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import hashlib
import json
import random
import time

from third_party.BeautifulSoup.BeautifulSoup import BeautifulSoup

from tests import cb


class MailTestCase(cb.CbTestCase):
  def setUp(self):
    super(MailTestCase, self).setUp()
    self.input_json = json.loads(self.read_file('input.json'))
    self.build_data = json.loads(self.input_json['message'])

  def test_html_format(self):
    import gatekeeper_mailer
    template = gatekeeper_mailer.MailTemplate(self.build_data['waterfall_url'],
                                              self.build_data['build_url'],
                                              self.build_data['project_name'],
                                              'test@chromium.org')

    _, html_content, _ = template.genMessageContent(self.build_data)

    expected_html = ' '.join(self.read_file('expected.html').splitlines())

    saw = str(BeautifulSoup(html_content)).split()
    expected = str(BeautifulSoup(expected_html)).split()

    self.assertEqual(saw, expected)

  def test_html_format_status(self):
    import gatekeeper_mailer
    status_header = ('Perf alert for "%(steps)s" on "%(builder_name)s"')
    template = gatekeeper_mailer.MailTemplate(self.build_data['waterfall_url'],
                                              self.build_data['build_url'],
                                              self.build_data['project_name'],
                                              'test@chromium.org',
                                              status_header=status_header)

    _, html_content, _ = template.genMessageContent(self.build_data)

    expected_html = ' '.join(self.read_file('expected_status.html')
                                  .splitlines())

    saw = str(BeautifulSoup(html_content)).split()
    expected = str(BeautifulSoup(expected_html)).split()

    self.assertEqual(saw, expected)

