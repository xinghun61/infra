#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import hashlib
import hmac
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

  @staticmethod
  def _hash_message(mytime, message, url, secret):
    salt = random.getrandbits(32)
    hasher = hmac.new(secret, message, hashlib.sha256)
    hasher.update(str(mytime))
    hasher.update(str(salt))
    client_hash = hasher.hexdigest()

    return {'message': message,
            'time': mytime,
            'salt': salt,
            'url': url,
            'hmac-sha256': client_hash,
           }

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

  def test_hmac_validation(self):
    from mailer import Email
    message = self.input_json['message']
    url = 'http://invalid.chromium.org'
    secret = 'pajamas'

    test_json = self._hash_message(time.time(), message, url, secret)
    # pylint: disable=W0212
    self.assertTrue(Email._validate_message(test_json, url, secret))

    # Test that a trailing slash doesn't affect URL parsing.
    test_json = self._hash_message(time.time(), message, url + '/', secret)
    # pylint: disable=W0212
    self.assertTrue(Email._validate_message(test_json, url, secret))

    tests = [
        self._hash_message(time.time() + 61, message, url, secret),
        self._hash_message(time.time() - 61, message, url, secret),
        self._hash_message(time.time(), message, url + 'hey', secret),
        self._hash_message(time.time(), message, url, secret + 'hey'),
    ]

    for test_json in tests:
      # pylint: disable=W0212
      self.assertFalse(Email._validate_message(test_json, url, secret))

    test_json = self._hash_message(time.time(), message, url, secret)
    test_json['message'] = test_json['message'] + 'hey'
    # pylint: disable=W0212
    self.assertFalse(Email._validate_message(test_json, url, secret))
