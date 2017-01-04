# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import cgi
import webapp2

from shared import utils


def _render(codereview_hostname, full_patchset_url,
            issue, patchset):  # pragma: no cover
  return open('templates/patch_status.html').read() % {
      'codereview_hostname_html': cgi.escape(codereview_hostname, quote=True),
      'codereview_hostname_js': json.dumps(cgi.escape(codereview_hostname,
                                                      quote=True)),
      'full_patchset_url_html': cgi.escape(full_patchset_url, quote=True),
      'issue': int(issue),
      'patchset': int(patchset),
    }


class PatchStatus(webapp2.RequestHandler): # pragma: no cover
  @utils.read_access
  def get(self, issue, patchset): # pylint: disable=W0221
    codereview_hostname = utils.guess_legacy_codereview_hostname(issue)
    full_patchset_url = utils.get_full_patchset_url(codereview_hostname, issue,
                                                    patchset)
    self.response.write(_render(
        codereview_hostname, full_patchset_url, issue, patchset))


class PatchStatusV2(webapp2.RequestHandler): # pragma: no cover
  @utils.read_access
  def get(self, codereview_hostname, issue, patchset): # pylint: disable=W0221
    full_patchset_url = utils.get_full_patchset_url(codereview_hostname, issue,
                                                    patchset)
    self.response.write(_render(
        codereview_hostname, full_patchset_url, issue, patchset))
