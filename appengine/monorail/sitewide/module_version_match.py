# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Page class for prober module version match checking."""

from framework import servlet

from google.appengine.api.modules import modules

class ModuleVersionMatch(servlet.Servlet):
  """Page class for module version match prober check."""

  def get(self, **kwargs):
    self.response.status = 200
    all_versions = set()
    for module in modules.get_modules():
      version = modules.get_default_version(module)
      if len(all_versions) > 0 and not version in all_versions:
        self.response.status = 500
      all_versions.add(version)

