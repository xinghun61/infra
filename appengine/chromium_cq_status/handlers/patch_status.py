# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2
import cgi

from shared.utils import (guess_legacy_codereview_hostname,
                          get_full_patchset_url)

class PatchStatus(webapp2.RequestHandler): # pragma: no cover
  def get(self, issue, patchset): # pylint: disable=W0221
    codereview_hostname = guess_legacy_codereview_hostname(issue)
    full_patchset_url = get_full_patchset_url(codereview_hostname, issue,
                                              patchset)
    self.response.write(open('templates/patch_status.html').read() % {
      'codereview_hostname': cgi.escape(codereview_hostname, quote=True),
      'full_patchset_url': cgi.escape(full_patchset_url, quote=True),
      'issue': cgi.escape(issue, quote=True),
      'patchset': cgi.escape(patchset, quote=True),
    })


class PatchStatusV2(webapp2.RequestHandler): # pragma: no cover
  def get(self, codereview_hostname, issue, patchset): # pylint: disable=W0221
    full_patchset_url = get_full_patchset_url(codereview_hostname, issue,
                                              patchset)
    self.response.write(open('templates/patch_status.html').read() % {
      'codereview_hostname': cgi.escape(codereview_hostname, quote=True),
      'full_patchset_url': cgi.escape(full_patchset_url, quote=True),
      'issue': cgi.escape(issue, quote=True),
      'patchset': cgi.escape(patchset, quote=True),
    })
