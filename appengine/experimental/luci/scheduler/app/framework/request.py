# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
from app.framework import auth
from app.framework.response import abort

class Request(object): # wraps a standard request
  def __init__(self, request):
    self.request = request
    self.auth = auth.Authenticator(self)
    try:
      if not self.request.body.strip():
        self.body = None
      else:
        self.body = json.loads(self.request.body)
    except:
      abort('Request body must be JSON')

  def __getattr__(self, name):
    return getattr(self.request, name)

  def get_or_abort(self, param):
    result = self.request.get(param, None)
    if result is None:
      abort('Required parameter \'%s\' is missing' % param)
    return result

