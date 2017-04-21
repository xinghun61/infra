# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from frontend.handlers import version
from frontend.handlers import report_crash


frontend_web_pages_handler_mappings = []
frontend_app = webapp2.WSGIApplication(
    frontend_web_pages_handler_mappings, debug=False)
