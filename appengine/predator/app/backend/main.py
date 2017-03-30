# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from backend.handlers import analyze_crash


backend_handler_mappings = []
backend_app = webapp2.WSGIApplication(backend_handler_mappings, debug=False)
