# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Initialize all the apps.

This module cannot be imported by tests (requires Datastore),
so keep it super simple.
"""

import admin_handler
import main

main_app = main.create_app()
admin_app = admin_handler.create_app()
