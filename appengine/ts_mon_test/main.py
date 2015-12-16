# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import httplib
import logging
import pprint
import time
import threading
import urllib2
import webapp2

import gae_ts_mon

from google.appengine.api.modules import modules

metric = gae_ts_mon.CounterMetric('test/dsansome/loadtest')


class IncrementHandler(webapp2.RequestHandler):
  def get(self):
    count = self.request.params['count']
    start = time.time()
    for _ in xrange(int(count)):
      metric.increment()
    end = time.time()

    self.response.write(end - start)


main_handlers = [
  (r'/inc', IncrementHandler),
]

app = webapp2.WSGIApplication(main_handlers, debug=True)
gae_ts_mon.initialize()
