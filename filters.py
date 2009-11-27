# Copyright (c) 2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from google.appengine.ext import webapp

register = webapp.template.create_template_register()


def spacify(value):
  """Makes spaces visible."""
  return re.sub('[ \t]', '&nbsp;', value)


register.filter(spacify)
