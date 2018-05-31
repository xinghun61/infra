# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission


class DetectCQFalseRejectionFlakes(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):  # pragma: no cover
    return {'return_code': 200}
