# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class ModuleShim(object):
  """Simple class used to bind a ThirdPartyPackagesApi instance to a class.

  This allows each third-party package to use API methods and access modules
  in a native, natural manner (e.g., "self.m.file").
  """

  def __init__(self, api):
    self._api = api

  def __getattr__(self, key):
    return getattr(self._api, key)
