# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from appengine_module.chromium_cq_status.model.cq_stats import CQStats

def get(handler): # pragma: no cover
  handler.response.write(open('templates/clear_stats.html').read())

def post(handler): # pragma: no cover
  if handler.request.get('all'):
    query = CQStats.query()
  else:
    projects = handler.request.get('projects').split(',')
    begin = handler.request.get('begin')
    end = handler.request.get('end')

    query = CQStats.query(CQStats.project.IN(projects))
    if begin:
      query = query.filter(
          CQStats.begin >= datetime.utcfromtimestamp(float(begin)))
    if end:
      query = query.filter(
          CQStats.end >= datetime.utcfromtimestamp(float(end)))

  handler.response.write('CQStats removed: [\n')
  for stats in query:
    handler.response.write('  %s,\n' % stats)
    stats.key.delete()
  handler.response.write(']\n')
