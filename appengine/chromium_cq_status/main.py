# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from handlers.admin_dispatch import AdminDispatch # pylint: disable-msg=W0403
from handlers.cron_dispatch import CronDispatch # pylint: disable-msg=W0403
from handlers.index import Index # pylint: disable-msg=W0403
from handlers.post import Post # pylint: disable-msg=W0403
from handlers.query import Query # pylint: disable-msg=W0403

handlers = [
  (r'/', Index),
  (r'/admin/(.*)', AdminDispatch),
  (r'/cron/(.*)', CronDispatch),
  (r'/post', Post),
  (r'/query(/.*)?', Query),
]

app = webapp2.WSGIApplication(handlers, debug=True)
