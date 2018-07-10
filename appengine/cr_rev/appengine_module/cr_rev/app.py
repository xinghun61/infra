# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from appengine_module.cr_rev import cr_rev_api
from appengine_module.cr_rev import views

api = cr_rev_api.get_routes()
app = views.get_routes()
