# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Actual WSGI app instantiations used from app.yaml.

Extracted to a separate module to avoid calling 'initialize' in unit tests
during module loading time.
"""

import main

endpoints_app, frontend_app, backend_app = main.initialize()
