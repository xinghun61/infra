# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import webapp2

from components import auth


class MainHandler(auth.AuthenticatingHandler):
  @auth.public
  def get(self):
    self.response.write('Hello world!')


main_handlers = [
      (r'/', MainHandler),
]

app = webapp2.WSGIApplication(main_handlers, debug=True)
