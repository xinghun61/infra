# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import webapp2

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(APP_DIR, 'third_party'))

# TODO(nodir): include ui and tasks
handlers = []

app = webapp2.WSGIApplication(handlers, debug=True)
