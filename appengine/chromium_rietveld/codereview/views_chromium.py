# Copyright 2008 Google Inc.
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

"""Views for Chromium port of Rietveld."""

import datetime
import logging
import random
import re

from google.appengine.datastore import datastore_query

from django.http import HttpResponse

from codereview import decorators as deco
from codereview import decorators_chromium as deco_cr
from codereview import models


### View handlers ###

@deco_cr.binary_required
def download_binary(request):
  """/<issue>/binary/<patchset>/<patch>/<content>

  Return patch's binary content.  If the patch is not binary, an empty stream
  is returned.  <content> may be 0 for the base content or 1 for the new
  content.  All other values are invalid.
  """
  response = HttpResponse(request.content.data, content_type=request.mime_type)
  filename = re.sub(
      r'[^\w\.]', '_', request.patch.filename.encode('ascii', 'replace'))
  response['Content-Disposition'] = 'attachment; filename="%s"' % filename
  return response
