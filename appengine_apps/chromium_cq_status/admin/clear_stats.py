# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.cq_stats import CQStats

def get(handler): # pragma: no cover
  handler.response.write(open('templates/clear_stats.html').read())

def post(handler): # pragma: no cover
  if handler.request.get('all'):
    stats_list = CQStats.query()
  else:
    stats_list = []
    for key in handler.request.get('keys').split(','):
      stats = CQStats.get_by_id(int(key))
      assert stats, '%s must exist.' % key
      stats_list.append(stats)

  handler.response.write('CQStats removed: [\n')
  for stats in stats_list:
    handler.response.write('  %s,\n' % stats)
    stats.key.delete()
  handler.response.write(']\n')
