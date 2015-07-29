# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Actual WSGI app instantiations used from app.yaml.

Needed to call 'main.initialize' from a separate module not imported in tests.
"""

import main

html_app, apis_app = main.initialize()
