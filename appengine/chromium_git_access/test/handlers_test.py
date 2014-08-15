# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Hack sys.path.
import setup_test_env  # pylint: disable=W0611

import datetime
import webapp2

from google.appengine.ext import ndb

from appengine.utils import testing
from appengine.chromium_git_access import handlers


class TestBasicHandlers(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(handlers.get_routes(), debug=True)

  def test_main_page(self):
    """Test that the root page renders."""
    response = self.test_app.get('/')
    self.assertEquals(200, response.status_int)

  def test_warmup(self):
    """Test that warmup works."""
    response = self.test_app.get('/_ah/warmup')
    self.assertEquals(200, response.status_int)


class TestAccessCheckHandler(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(handlers.get_routes(), debug=True)

  canned_access_check = {
    'checker_version': 0,
    'chrome_internal_netrc_email': None,
    'chromium_netrc_email': 'blah@chromium.org',
    'git_user_email': 'blah@chromium.org',
    'git_user_name': 'Blah Blahovic',
    'is_git': True,
    'is_home_set': True,
    'is_using_netrc': True,
    'netrc_file_mode': 0600,
    'platform': 'linux2',
    'push_duration_ms': 5000,
    'push_log': 'It just worked!!!111',
    'push_works': True,
    'username': 'blah',
  }

  def post_check(self, **access_check):
    """Helper to post JSON to the handler."""
    return self.test_app.post_json(
        '/git_access/api/v1/reports/access_check',
        {'access_check': access_check},
        expect_errors=True)

  @staticmethod
  def fetch_entries():
    """Fetches all AccessCheckEntry from datastore."""
    return list(handlers.AccessCheckEntry.query())

  def test_submit_works(self):
    """Submitting reports add it to datastore."""
    mocked_now = datetime.datetime(1963, 11, 22)
    self.mock_now(mocked_now)

    self.assertEquals(0, len(self.fetch_entries()))
    response = self.post_check(**self.canned_access_check)
    self.assertEquals(200, response.status_int)
    self.assertEquals({'ok': True}, response.json_body)
    # Read it back from datastore.
    entries = self.fetch_entries()
    self.assertEquals(1, len(entries))
    self.assertEquals(
        ndb.Key(
            'AccessCheckEntryShard_v1',
            '52',
            'AccessCheckEntry',
            '523e0b836ceaf0583017c23e8cab77908e8fc932'),
        entries[0].key)
    self.assertEquals(
        {
          'checker_version': 0,
          'chrome_internal_netrc_email': None,
          'chromium_netrc_email': u'blah@chromium.org',
          'git_user_email': u'blah@chromium.org',
          'git_user_name': u'Blah Blahovic',
          'is_git': True,
          'is_home_set': True,
          'is_using_netrc': True,
          'netrc_file_mode': 384,
          'platform': u'linux2',
          'push_duration_ms': 5000,
          'push_log': u'It just worked!!!111',
          'push_works': True,
          'timestamp': datetime.datetime(1963, 11, 22, 0, 0),
          'username': u'blah',
      }, entries[0].to_dict())

  def test_no_access_check_dict(self):
    """'access_check' dict is required."""
    response = self.test_app.post_json(
        '/git_access/api/v1/reports/access_check',
        {'blah': {}},
        expect_errors=True)
    self.assertEquals(400, response.status_int)
    self.assertEquals({'text': 'Missing access_check dict'}, response.json_body)

  def test_missing_some_properties(self):
    """All known properties are required."""
    request = self.canned_access_check.copy()
    request.pop('username')
    response = self.post_check(**request)
    self.assertEquals(400, response.status_int)
    self.assertEquals(
        {'text': 'Incomplete access_check dict'}, response.json_body)

  def test_wrong_type(self):
    request = self.canned_access_check.copy()
    request['checker_version'] = 'I am totally an integer'
    response = self.post_check(**request)
    self.assertEquals(400, response.status_int)
    self.assertEquals(
        {'text': 'Key checker_version has invalid type'}, response.json_body)

  def test_extra_properties(self):
    """Extra properties are ignored."""
    response = self.post_check(extra=1, **self.canned_access_check)
    self.assertEquals(200, response.status_int)
    self.assertEquals({'ok': True}, response.json_body)

  def test_resubmit_skipped(self):
    """Submitting same report twice doesn't create second entity."""
    self.assertEquals(0, len(self.fetch_entries()))
    self.post_check(**self.canned_access_check)
    self.post_check(**self.canned_access_check)
    self.assertEquals(1, len(self.fetch_entries()))
