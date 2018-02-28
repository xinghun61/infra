# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging

from framework import jsonfeed


class ComponentLog(jsonfeed.JsonFeed):
  """Handler for logging a user accepting a suggested component."""

  def HandleRequest(self, mr):

    text = mr.request.POST.items()
    logging.info(text)
