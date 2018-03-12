# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission

from services import build_ahead


class BuildAhead(BaseHandler):
  """Perform a full build on idle bots to reduce latency of compile analyses."""

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    build_ahead.BuildCaches()
