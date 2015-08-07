# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides a JSON endpoint for builder data as Trace Viewer Events

Given a master, builder, and build ID, queries chrome-build-extract and
converts the resulting JSON to a format parseable by Trace Viewer.
"""

import contextlib
import urllib2
import json
import webapp2

from shared.utils import cross_origin_json
from handlers.patch_timeline_data import (
  TraceViewerEvent,
  MetaEvent,
)

class BuilderTimelineData(webapp2.RequestHandler): # pragma: no cover
  @cross_origin_json
  def get(self, master, builder, buildId, attempt_string):
    data = get_data(master, builder, buildId)
    events = []
    if data:
      for event in create_events(data, master, builder, buildId, 
                                 attempt_string):
        events.append(event.to_dict())
    return events


def get_data(master, builder, buildId): # pragma: no cover
  url = ('http://chrome-build-extract.appspot.com/p/' + master + '/builders/'
         + builder + '/builds/' + buildId + '?json=1')
  with contextlib.closing(urllib2.urlopen(url)) as response:
    data = json.load(response)
  # If the builder is running, chrome-build-extract returns {'error': '404'}
  if data.get('error'):
    return None
  else:
    return data


def create_events(data, master, builder, buildId, 
                  attempt_string): # pragma: no cover
  steps = data['steps']
  state = 'cq_build_failed' if data.get('failed_steps') else 'cq_build_passed'
  for step in steps:
    cname = state if step['name'] == 'steps' else None
    yield TraceViewerEvent(step['name'], master, 'B', step['times'][0],
                           attempt_string, builder, cname, {'id': buildId})
    yield TraceViewerEvent(step['name'], master, 'E', step['times'][1],
                           attempt_string, builder, cname, {'id': buildId})
