# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Monkey patching of GCS library to use real GCS on local dev server."""

import functools
import logging

from google.appengine.ext import ndb

from cloudstorage import common
from cloudstorage import rest_api

from components import auth
from components import utils


# Unpatched rest_api._RestApi.get_token_async.
_original_get_token_async = None


def patch_cloudstorage_lib(service_account_key):
  """Makes cloudstorage library talk to real GCS using our own token.

  Note that cloudstorage.set_access_token() is partially broken. _RestApi class
  ignores it. See rest_api._RestApi.urlfetch_async (get_token_async call that
  unconditionally overwrites previously set token). Setting the token disables
  the usage of local mocks though, so we set it anyway (to some garbage, it
  doesn't matter).
  """
  assert utils.is_local_dev_server()
  common.set_access_token('lalala')

  global _original_get_token_async
  if _original_get_token_async is None:
    logging.warning('Monkey patching GCS library to use valid token')
    _original_get_token_async = rest_api._RestApi.get_token_async

  # pylint: disable=unused-argument
  @functools.wraps(_original_get_token_async)
  def patched_get_token_async(self, refresh=False):
    fut = ndb.Future()
    fut.set_result(auth.get_access_token(self.scopes, service_account_key)[0])
    return fut

  rest_api._RestApi.get_token_async = patched_get_token_async
