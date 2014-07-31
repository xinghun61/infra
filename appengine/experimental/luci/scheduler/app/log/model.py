# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools
from google.appengine.ext import ndb

logstore_pair = ('LogStore', 'logstore')
def _key_from_category(category):
  namespaces = category.split('/')
  return ndb.Key(pairs = [logstore_pair] +
                         map(lambda x : ('LogNamespace', x), namespaces))

class LogSet(ndb.Model):
  lines = ndb.StringProperty(repeated = True)
  timestamp = ndb.DateTimeProperty(required = True, auto_now_add = True)

  def __init__(self, category = None, parent = None, *args, **kwargs):
    if category is not None:
      parent = _key_from_category(category)
    super(LogSet, self).__init__(parent = parent, *args, **kwargs)

def log(category, lines):
  if isinstance(lines, basestring):
    lines = [lines]
  logset = LogSet(category = category)
  logset.lines = lines
  logset.put()

def get_logs(category):
  query = LogSet.query(ancestor = _key_from_category(category))
  logsets = query.order(LogSet.timestamp).fetch()
  loglines = map(lambda x : x.lines, logsets) # list of lists
  return list(itertools.chain.from_iterable(loglines)) # flatten
