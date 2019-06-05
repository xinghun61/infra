# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet for Content Security Policy violation reporting.
See http://www.html5rocks.com/en/tutorials/security/content-security-policy/
for more information on how this mechanism works.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import webapp2
import logging


class CSPReportPage(webapp2.RequestHandler):
  """CSPReportPage serves CSP violation reports."""

  def post(self):
    logging.error('CSP Violation: %s' % self.request.body)
