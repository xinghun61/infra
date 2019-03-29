# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This handler redirects the old URLs to the corresponding new ones.

Only GET requests will be redirected, and all parameters in the original URL
will be preserved in the URL redirected to. If a URL path changes, it has to be
added to the mapping below for backward compatibility.
"""

from gae_libs.handlers.base_handler import BaseHandler, Permission

# Redirection mappings.
# {
#   'current.hostname.com': {
#      'hostname': 'new.hostname.com',  # Optional. Default to the current host.
#      'url-mappings': {
#          '/old/url/path': '/new/url/path',
#      }
#   }
# }
_REDIRECTION_MAPPING = {
    'findit-for-me.appspot.com': {
        'hostname': 'analysis.chromium.org',
        'url-mappings': {
            '/coverage':
                '/p/chromium/coverage',
            '/flake/occurrences':
                '/p/chromium/flake-portal/flakes/occurrences',
            '/flake/report':
                '/p/chromium/flake-portal/report',
            '/flake/report/component':
                '/p/chromium/flake-portal/report/component',
            '/ranked-flakes':
                '/p/chromium/flake-portal/flakes',
            '/waterfall/flake':
                '/p/chromium/flake-portal/analysis/analyze',
            '/waterfall/build-failure':
                '/waterfall/failure',
            '/waterfall/flake/flake-culprit':
                '/p/chromium/flake-portal/analysis/culprit',
            '/waterfall/list-analyses':
                '/waterfall/list-failures',
            '/waterfall/list-flakes':
                '/p/chromium/flake-portal/analysis',
        }
    },
    'analysis.chromium.org': {
        'url-mappings': {
            '/p/chromium/flake-portal/analysis/analyze/flake-culprit':
            '/p/chromium/flake-portal/analysis/culprit',
        }
    }
}
_REDIRECTION_MAPPING['findit-for-me-staging.appspot.com'] = {
    'url-mappings':
        _REDIRECTION_MAPPING['findit-for-me.appspot.com']['url-mappings'],
}


class URLRedirect(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandelPost(self):
    return self.CreateError(
        'Wrong destination URL for a post request. Please file a bug '
        'by clicking the button at the bottom right corner.', 400)

  def _GetHostAndPath(self):
    """Returns the hostname and path in the URL. This is for mocking in test."""
    return self.request.host, self.request.path

  def HandleGet(self):
    hostname, path = self._GetHostAndPath()

    setting = _REDIRECTION_MAPPING.get(hostname, {})
    new_hostname = setting.get('hostname', hostname)

    new_path = setting.get('url-mappings', {}).get(path, path)
    if new_hostname == hostname and new_path == path:
      return self.CreateError('Page not found', 404)

    new_url = 'https://%s%s' % (new_hostname, new_path)

    query_string = self.request.query_string
    if query_string:
      new_url = '%s?%s' % (new_url, query_string)

    return self.CreateRedirect(new_url)
