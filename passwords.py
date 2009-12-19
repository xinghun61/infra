# Copyright (c) 2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Password management page.

It really just exist to create the first entry, so the databse is created and
can be managed with the admin-console. *Sigh*"""

import hashlib

from google.appengine.ext import webapp

import base_page
from utils import work_queue_only


class PasswordsPage(webapp.RequestHandler):
  """This page is a potential security hole. Don't enable it unless
  necessary."""
  @work_queue_only
  def get(self):
    raw_password = self.request.get('password')
    if raw_password:
      password_sha1 = password_sha1=hashlib.sha1(raw_password).hexdigest()
      # Look if the password already exists first.
      if base_page.Passwords.gql('WHERE password_sha1 = :1',
                                 password_sha1).get():
        return
      password = base_page.Passwords(password_sha1=password_sha1)
      password.put()
