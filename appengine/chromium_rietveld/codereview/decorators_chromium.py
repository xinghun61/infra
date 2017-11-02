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

"""Decorators for Chromium port of Rietveld."""

import functools
import mimetypes

from . import decorators as deco
from . import responses


def binary_required(func):
  """Decorator that processes the content argument.

  Attributes set on the request:
   content: a Content entity.
  """

  @functools.wraps(func)
  @deco.patch_required
  def binary_wrapper(request, content_type, *args, **kwds):
    if content_type == "0":
      content_key = request.patch.content_key
    elif content_type == "1":
      content_key = request.patch.patched_content_key
      if not content_key or not content_key.get().data:
        # The file was not modified. It was likely moved without modification.
        # Return the original file.
        content_key = request.patch.content_key
    else:
      # Other values are erroneous so request.content won't be set.
      return responses.HttpTextResponse(
          'Invalid content type: %s, expected 0 or 1' % content_type,
          status=404)
    request.mime_type = mimetypes.guess_type(request.patch.filename)[0]
    request.content = content_key.get()
    return func(request, *args, **kwds)

  return binary_wrapper
