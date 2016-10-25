# Copyright 2013 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import urlparse

from google.appengine.api import app_identity

from django.conf import settings

IS_DEV = os.environ['SERVER_SOFTWARE'].startswith('Dev')  # Development server


def get_preferred_domain(project=None, default_to_appid=True):
  """Returns preferred domain for a given project."""
  projects_prefs = settings.PREFERRED_DOMAIN_NAMES.get(settings.APP_ID, {})
  preferred_domain = projects_prefs.get(project)
  if not preferred_domain:
    preferred_domain = projects_prefs.get(None)
  if not preferred_domain:
    if default_to_appid:
      preferred_domain = '%s.appspot.com' % app_identity.get_application_id()
  return preferred_domain


def rewrite_url(url, project=None):
  """Returns a url using the preferred domain name for this app instance."""
  parts = list(urlparse.urlsplit(url))
  new_domain = get_preferred_domain(project=project, default_to_appid=False)
  if new_domain:
    parts[1] = new_domain
  return urlparse.urlunsplit(parts)
