# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from app.framework.response import failure, abort

# TODO(nbharadwaj) at some point, we'll need more granular access control
# oh and real authentication, of course :p
class User(object):
  def __init__(self, id):
    self.id = id

  def is_worker(self):
    return True

class Authenticator(object):
  def __init__(self, request):
    self.request = request

  # Returns None if not authenticated
  def get_current_user(self):
    uid = self.request.get('uid', None)
    if uid is None:
      return None
    else:
      return User(uid)

  def require_entity(self, cls):
    user = self.get_current_user()
    if not user.is_worker():
      abort(failure('Invalid credentials: must be a valid worker'))

    worker = cls.get_by_id(user.id)
    if worker is None:
      abort(failure('Invalid credentials: must be a valid worker'))

    return worker
