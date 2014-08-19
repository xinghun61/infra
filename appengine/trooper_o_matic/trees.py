# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Lists the masters for the given tree.
"""
import base64
import json
import logging
import re

from google.appengine.api import urlfetch

URL = ('https://chromium.googlesource.com/chromium/tools/build/+'
       '/master/scripts/slave/gatekeeper_trees.json?format=text')

MASTER_RE = r'https://build.chromium.org/p/(.*)'


def GetMastersForTree(tree): # pragma: no cover
  response = urlfetch.fetch(URL)
  if response.status_code != 200:
    logging.error('Error %d fetching %s', response.status_code, URL)
    return None
  tree_info = json.loads(base64.b64decode(response.content)).get(tree)
  return [re.match(MASTER_RE, m).group(1) for m in tree_info.get('masters')]
