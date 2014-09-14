# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from appengine_module.cr_rev import views

app = webapp2.WSGIApplication([
    ('/_ah/warmup', views.StartPage),
    ('/_ah/start', views.StartPage),
    (r'/(\w+)(/.*)?', views.Redirect),
    ('/', views.MainPage),
])
