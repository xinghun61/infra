# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import views  # pylint: disable=W0403

app = webapp2.WSGIApplication([
    ('/_ah/warmup', views.StartPage),
    ('/', views.MainPage),
])
