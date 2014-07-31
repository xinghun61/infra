# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2
from functools import wraps

from app.framework.response import success, failure, abort, FrameworkAbortError
from app.framework.model import DefaultRootModel
from app.framework.request import Request


class Application(webapp2.WSGIApplication):
  def __init__(self, auth_required=False, *args, **kwargs):
    super(Application, self).__init__(*args, **kwargs)
    self.auth_required = auth_required
    self.router.set_dispatcher(self.__class__.framework_dispatcher)

  @staticmethod
  def framework_dispatcher(router, request, response):
    rv = router.default_dispatcher(request, response)
    if isinstance(rv, basestring):
      rv = webapp2.Response(rv)
    return rv

  def route(self, path, methods=None):
    if methods is None:
      methods = ['GET']

    def wrapper(handler):
      @wraps(handler)
      def wrapped_handler(request, *args, **kwargs):
        try:
          request = Request(request)

          if self.auth_required and request.auth.get_current_user() is None:
            return failure('Authentication required')

          return handler(request, *args, **kwargs)
        except FrameworkAbortError as e:
          return e.response

      self.router.add(webapp2.Route(path,
                                    handler=wrapped_handler,
                                    name=handler.__name__,
                                    methods=methods))
      return wrapped_handler

    return wrapper
