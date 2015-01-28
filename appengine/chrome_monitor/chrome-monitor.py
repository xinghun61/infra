# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# chrome-monitor.py: Part of the chrome-monitor Appengine App.

import calendar
import collections
import datetime
import jinja2
import json
import logging
import os
import time
import urllib
import webapp2

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb

# Set up the rendering environment.
jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                   'templates')),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])
jinja_environment.filters['json_dumps'] = json.dumps

# Seed the default masters to watch.
CBE_MASTER_URL = 'http://chrome-build-extract.appspot.com/get_master/%s'
DEFAULT_MASTER = [
    'chromium',
    'chromium.chrome',
    'chromium.chromedriver',
    'chromium.chromiumos',
    'chromium.endure',
    'chromium.fyi',
    'chromium.gatekeeper',
    'chromium.git',
    'chromium.gpu',
    'chromium.gpu.fyi',
    'chromium.linux',
    'chromium.lkgr',
    'chromium.mac',
    'chromium.memory',
    'chromium.memory.fyi',
    'chromium.perf',
    'chromium.swarm',
    'chromium.webkit',
    'chromium.webrtc',
    'chromium.webrtc.fyi',
    'chromium.win',
    'client.chromeoffice',
    'client.v8',
    'tryserver.blink',
    'tryserver.chromium.gpu',
    'tryserver.chromium.linux',
    'tryserver.chromium.mac',
    'tryserver.chromium.win',
    'tryserver.v8',
]

# These are the steps that we will categorize as "update"
UPDATE_STEPS = [
    'update_scripts',
    'update',
    'apply_issue',
    'cleanup_temp'
]

# Configure how graph pruning works.
# This is a list of (Time Ago, Time Window) tuples.
PRUNE_CONFIG = [
    # Points older than 4 hours have 10 min resolutions.
    (datetime.timedelta(hours=4), datetime.timedelta(minutes=10)),
    # Points older than 24 hours have 30 min resolutions.
    (datetime.timedelta(hours=24), datetime.timedelta(minutes=30)),
    # Points older than 7 days have 3 hr resolutions.
    (datetime.timedelta(days=7), datetime.timedelta(hours=3)),
]

# We whitelist these graphs to enable pruning so that we can view more
# historical data.
WHITELIST_FOR_PRUNING = [
    'tryserver.blink',
    'tryserver.chromium.gpu',
    'tryserver.chromium.linux',
    'tryserver.chromium.mac',
    'tryserver.chromium.win',
    'tryserver.v8',
]


def get_timedelta(times):
  if times[1]:
    return times[1] - times[0]
  else:
    return 0

########
# Models
########
class GraphModel(ndb.Model):
  tags = ndb.StringProperty(repeated=True)
  name = ndb.StringProperty()
  y_label = ndb.StringProperty()
  config = ndb.JsonProperty(compressed=True)


class PointModel(ndb.Model):
  graph = ndb.KeyProperty(kind=GraphModel)
  timestamp = ndb.DateTimeProperty(auto_now_add=True)
  values = ndb.JsonProperty(compressed=True)


class TagModel(ndb.Model):
  name = ndb.StringProperty()


############
# Decorators
############
def render(template_filename):
  def _render(fn):
    def wrapper(self, *args, **kwargs):
      results = fn(self, *args, **kwargs)
      template = jinja_environment.get_template(template_filename)
      self.response.out.write(template.render(results))
    return wrapper
  return _render


def render_json(fn):
  # The function is expected to return a dict, and we want to render json.
  def wrapper(self, *args, **kwargs):
    results = fn(self, *args, **kwargs)
    self.response.out.write(json.dumps(results))
  return wrapper


def maybe_render_json(template_filename, *o_args, **o_kwargs):
  """If the variable 'json' exists in the request, return a json object.

  Otherwise render the page using the template.  Useful if we later want to
  hook the page to another appengine app in the future."""
  def _render(fn):
    def wrapper(self, *args, **kwargs):
      if self.request.get('json'):
        if not self.request.get('text'):
          self.response.headers['Content-Type'] = 'application/json'
        results = fn(self, *args, **kwargs)
        self.response.out.write(json.dumps(results))
      else:
        final_render = render(template_filename, *o_args, **o_kwargs)(fn)
        return final_render(self, *args, **kwargs)
    return wrapper
  return _render


#########
# Helpers
#########

def _is_cq_job(build_info):
  """Checks if the "requestor" property is present, and if
  commit-bot@chromium.org is the requestor."""
  properties = dict([(k, v) for k, v, _ in build_info['properties']])
  return 'commit-bot@chromium.org' == properties.get('requester')


def add_stats(graph_name, data, prefix='', config=None, *args, **kwargs):
  """Given a list of values, break it down to to stats and graph it.

  Emits min, q1, median, q3, max, and mean of a series of data."""
  config = config or {}

  if data:
    data = sorted(data)
    p_min = data[0]
    p_q1 = data[len(data)/4]
    p_q2 = data[len(data)/2]
    p_q3 = data[len(data)*3/4]
    p_max = data[-1]
    p_mean = sum(data)/len(data)
  else:
    p_min = p_q1 = p_q2 = p_q3 = p_max = p_mean = 0
  points = {
      prefix + 'min': p_min,
      prefix + 'q1': p_q1,
      prefix + 'median': p_q2,
      prefix + 'q3': p_q3,
      prefix + 'max': p_max,
      prefix + 'mean': p_mean
  }
  config['stats'] = True
  add_points(graph_name, points, *args, config=config, **kwargs)


def add_points(graph_name, points, y_label=None, tags=None, config=None):
  """Add a set of new points to a graph.

  Creates the graph if it does not yet exist.
  """
  config = config or {}

  graph_q = GraphModel.query(GraphModel.name == graph_name).fetch(1)
  if not graph_q:
    graph = GraphModel(name=graph_name, config={})
    graph.put()
  else:
    graph = graph_q[0]

  if 'point_names' not in graph.config:
    graph.config['point_names'] = []
    graph.put()
  if not graph.y_label or graph.y_label != y_label:
    if y_label:
      graph.y_label = y_label
      graph.put()
  if tags:
    for tag in tags:
      if tag not in graph.tags:
        graph.tags.append(tag)
        graph.put()
        tag_q = TagModel.query(TagModel.name == tag).fetch(1)
        if not tag_q:
          TagModel(name=tag).put_async()
  for k, v in config.iteritems():
    if v != graph.config.get(k):
      graph.config[k] = v
      graph.put()

  point = PointModel(graph=graph.key, values=points)
  point.put()

  for point_name in points.keys():
    if point_name not in graph.config['point_names']:
      graph.config['point_names'].append(point_name)
      graph.put()


def get_builders(master):
  """Get the list of builders from a master from CBE.

  Returns the list in a (platform, master name, builder name) format.
  """
  url = CBE_MASTER_URL % master
  max_retries = 3
  retries = max_retries
  data = None
  while retries > 0 and not data:
    try:
      data = json.loads(urlfetch.fetch(url, deadline=300).content)
    except urlfetch.DownloadError:
      # Exponential backoff
      time.sleep(2 ** (max_retries - retries))
      continue
  if not data:
    raise urlfetch.DownloadError('Could not fetch %s' % url)
  platforms = ['ios', 'android', 'cros', 'win', 'mac', 'linux']
  results = []
  for builder in data['builders']:
    platform = 'other'
    for cur_platform in platforms:
      if cur_platform in builder:
        platform = cur_platform
        break
    results.append((platform, master, builder))
  return results


def get_graph_ticks(ts):
  """Configure how the graph looks.

  Each item in GRAPH_TICKS is a graph that appears in a graph page.
  The first item in the graph tick is what that grpah is called.
  The second item is a list of vertical tick marks in the graph.
  """
  MINUTE = 60
  HOUR = 60 * MINUTE
  DAY = 24 * HOUR
  WEEK = 7 * DAY
  return [
      ['1hr',
       [(ts - 60 * MINUTE),  # 60 minutes ago.
        (ts - 45 * MINUTE),  # 45 minutes ago.
        (ts - 30 * MINUTE),  # 30 minutes ago.
        (ts - 15 * MINUTE),  # 15 minutes ago.
        (ts)]],           # Now.
      ['4hr', [(ts - 4 * HOUR),  # 4 hours ago.
               (ts - 3 * HOUR),  # 3 hours ago.
               (ts - 2 * HOUR),  # 2 hours ago.
               (ts - HOUR),      # 1 hour ago.
               (ts)]],              # Now.
      ['24hr', [(ts - 24 * HOUR),  # 24 hours ago.
                (ts - 18 * HOUR),  # 18 hours ago.
                (ts - 12 * HOUR),  # 12 hours ago.
                (ts - 6 * HOUR),   # 6 hours ago.
                (ts)]],               # Now.
      ['7d', [(ts - 7 * DAY),  # 7 days ago.
              (ts - 6 * DAY),  # 6 days ago.
              (ts - 5 * DAY),  # 5 days ago.
              (ts - 4 * DAY),  # 4 days ago.
              (ts - 3 * DAY),  # 3 days ago.
              (ts - 2 * DAY),  # 2 days ago.
              (ts - 1 * DAY),  # 1 day ago.
              (ts)]],                    # Now.
      ['28d', [(ts - 4 * WEEK),  # 4 weeks ago.
               (ts - 3 * WEEK),  # 3 weeks ago.
               (ts - 2 * WEEK),  # 2 weeks ago.
               (ts - 1 * WEEK),  # 1 weeks ago.
               (ts)]]                    # Now.
  ]


########################
# User Facing End points
########################
class ListGraphs(webapp2.RequestHandler):
  """List all known graphs."""

  @render('list_graphs.html')
  def get(self, tags=''):
    if tags:
      tags = tags.split('/')

    graph_q = GraphModel.query()
    for tag in tags:
      graph_q = graph_q.filter(GraphModel.tags == tag)

    known_tags = collections.defaultdict(lambda: 0)
    graphs = []

    for graph in graph_q.fetch():
      graphs.append({
          'name': graph.name,
          'tags': graph.tags,
          'config': graph.config
      })
      for tag in graph.tags:
        known_tags[tag] += 1

    all_tags = [tag.name for tag in TagModel.query().fetch()]
    logging.info(sorted(known_tags.iteritems()))
    return {
        'current_tags': tags,
        'graphs': sorted(graphs, key=lambda x: x['name']),
        'all_tags': sorted(all_tags),
        # Sort by name.
        'tags': sorted(known_tags.iteritems(), key=lambda x: x[0])
    }


class ViewGraph(webapp2.RequestHandler):
  """Graph points associated with a GraphModel.

  We want to return data for: 1hr, 4hrs, 24hrs, 7d, 28d.
  """
  @maybe_render_json('view_graph.html')
  def get(self, graph_name):
    graph_q = GraphModel.query(GraphModel.name == graph_name).fetch(1)
    if not graph_q:
      self.error(404)
      return {'status': 'Error - %s not found' % graph_name}
    graph = graph_q[0]

    num_points = int(self.request.get('num_points', 100000))

    days_since = int(self.request.get('days', '28'))
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days_since)
    points_q = PointModel.query(PointModel.graph == graph.key,
                                PointModel.timestamp > since)
    points_q = points_q.order(-PointModel.timestamp)
    point_names = graph.config['point_names']
    all_points = []  # List of list, aka a matrix.
    Point = collections.namedtuple('Point', ['time'] + point_names)
    for point in points_q.fetch(num_points):
      all_points.append(Point(
          calendar.timegm(point.timestamp.utctimetuple()), **point.values))
    logging.info('Fetched %d points', len(all_points))

    if self.request.get('json'):
      return {
          'point_names': ['time'] + point_names,
          'data': all_points,
          'graph_name': graph.name,
          'graph_y': graph.y_label,
          'graph': graph.config,
      }

    ts = int(time.time())

    # Convert to a javascript readable format.
    graph_ticks = get_graph_ticks(ts)
    for graph_tick in graph_ticks:
      graph_tick[1] = ['new Date(%d)' % (tick * 1000) for tick in graph_tick[1]]

    return {
      'point_names': ['time'] + point_names,
      'data': all_points,
      'graph_name': graph.name,
      'graph_y': graph.y_label,
      'graph': graph.config,
      'graph_ticks': graph_ticks
    }


################
# Task Endpoints
################

class UpdateBuildQueue(webapp2.RequestHandler):
  """Get information on the queue status and update graphs.

  Graphs the following information:
    * Build Queue & Running Builds (win/mac/linux/all)
  """
  @render_json
  def get(self, master):
    url = 'http://chrome-build-extract.appspot.com/get_master/%s' % master
    master_data = json.loads(urlfetch.fetch(url, deadline=600).content)
    created_timestamp = master_data.get('created')
    logging.debug('Fetched %s. Created timestamp: %s'
                  % (url, created_timestamp))
    points = {
        'all': {},
        'win': {},
        'linux': {},
        'mac': {},
        'android': {},
        'ios': {},
        'cros': {},
        'presubmit': {},
    }
    for data in points.itervalues():
      data['pending'] = 0
      data['running'] = 0

    for builder_name, builder_data in master_data['builders'].iteritems():
      urls = [
          '/tasks/update_builder_success_rate/%s/%s/100' % (
              master, builder_name),
          '/tasks/update_builder_times/%s/%s/100' % (
              master, builder_name)
      ]
      for url in urls:
        url = urllib.quote(url)
        logging.debug('Adding %s' % url)
        taskqueue.add(url=url)

      pending = builder_data['pendingBuilds']
      current = len(builder_data['currentBuilds'])
      points['all']['pending'] += pending
      points['all']['running'] += current
      builder_tags = [master, builder_name, 'build_queue', 'builder']

      for platform, data in points.items():
        if platform in builder_name:
          data['pending'] += pending
          data['running'] += current
          builder_tags.append(platform)
          break
      add_points('%s Builder %s Queue/Running' % (master, builder_name),
                 {'pending': pending, 'running': current},
                 y_label='Num Builds',
                 tags=builder_tags)

    for platform, data in points.iteritems():
      add_points('%s Platform %s Queue/Running' % (master, platform),
                 data,
                 y_label='Num Builds',
                 tags=[master, platform, 'build_queue', 'platform'])

    return {
        'data': master_data,
        'point_names': points
    }

  def post(self, *args, **kwargs):
    return self.get(*args, **kwargs)


class UpdateBuilderSuccessRate(webapp2.RequestHandler):
  """Get information on the success rate and update graphs.

  Graphs the following information:
    * Builder Success Rate
  """
  @render_json
  def get(self, master, builder, num_builds):
    url = ('https://chrome-build-extract.appspot.com/get_builds'
           '?master=%s&builder=%s&num_builds=%s' % (
               master, builder, num_builds))
    builds_data = json.loads(urlfetch.fetch(url, deadline=600).content)

    successes = 0
    infra_successes = 0
    total = 0

    for build_data in builds_data['builds']:
      total += 1
      # Guide for decoding buildbot status (buildbot/status/results.py):
      #  0 - SUCCESS
      #  1 - WARNINGS
      #  2 - FAILURE
      #  3 - SKIPPED
      #  4 - EXCEPTION
      #  5 - RETRY
      if build_data.get('results') in [0, 1]:
        successes += 1
      if build_data.get('results') in [0, 1, 2]:
        infra_successes += 1

    add_points('%s Builder %s Success Rate (Last %s Builds)' % (
                   master, builder, num_builds),
               {
                 'success_rate': successes * 100 / max(1, total),
                 'infra_success_rate': infra_successes * 100 / max(1, total),
               },
               y_label='percent',
               tags=[master, builder, 'success_rate', 'builder'])

    return {
        'data': builds_data,
    }

  def post(self, *args, **kwargs):
    return self.get(*args, **kwargs)


class UpdateBuilderTimes(webapp2.RequestHandler):
  """Get information on the build times and update graphs.

  Graphs the following information:
    * Builder Times Stats
  """
  @render_json
  def get(self, master, builder, num_builds):
    url = 'https://%s' % urllib.quote(
        'chrome-build-extract.appspot.com/get_builds'
        '?master=%s&builder=%s&num_builds=%s' % (
            master, builder, num_builds))
    builds_data = json.loads(urlfetch.fetch(url, deadline=600).content)

    times = []

    for build_data in builds_data['builds']:
      # Only process complete builds.
      if ('times' not in build_data or
          len(build_data['times']) < 2 or
          not build_data['times'][0] or
          not build_data['times'][1]):
        continue

      times.append((build_data['times'][1] - build_data['times'][0]) / 60.0)

    add_stats('%s Builder %s Times (Last %s Builds)' % (
                   master, builder, num_builds),
              times,
              y_label='minutes',
              tags=[master, builder, 'builder_time', 'builder'])

    return {
        'data': builds_data,
    }

  def post(self, *args, **kwargs):
    return self.get(*args, **kwargs)


class UpdateCQ(webapp2.RequestHandler):
  """Get information on the CQ status and update graphs.

  Graphs the following information:
    * Commit Queue age.  (Min/Q1/Median/Mean/Q3/Max)
    * Commit Queue time. (Min/Q1/Median/Mean/Q3/Max)
    * Commits per hour.  (Last 1hr, 4hr, 24hr)
    * Commit Queue Length.
  """
  @render_json
  def get(self):
    # Run a search for all issues that have the commit box checked, but not
    # yet closed.  Also we want messages.
    CQ_URL = ('https://codereview.chromium.org/search?format=json&commit=2&'
              'closed=3&limit=1000&with_messages=1')
    cq_issues = json.loads(
        urlfetch.fetch(CQ_URL, deadline=600).content)['results']
    # Filter out NO_TRY jobs.
    cq_issues = [issue for issue in cq_issues
                 if 'no_try' not in issue['description'].lower()]


    # Calculate quartiles.
    issue_times = []
    for issue in cq_issues:
      for msg in reversed(issue['messages']):
        if 'cq is trying da patch' in msg['text'].lower():
          msg_date = datetime.datetime.strptime(msg['date'],
                                                '%Y-%m-%d %H:%M:%S.%f')
          delta = datetime.datetime.utcnow() - msg_date
          issue_times.append(int(delta.total_seconds() / 60))
        break

    # Save the results as new data points.
    add_stats('CQ Length',
              issue_times,
              y_label='Minutes',
              tags=['cq', 'length'],
              config={'log_scale': True})


  def post(self, *args, **kwargs):
    return self.get(*args, **kwargs)


class PruneGraph(webapp2.RequestHandler):
  """Compact the number of points we have.

  See PRUNE_CONFIG up at the top of the file for the pruning configs.
  This is called by the UpdateAll class, which queues all graphs into the
  task queue.
  """

  def get(self, graph_id):
    graph = GraphModel.get_by_id(int(graph_id))
    logging.info('Pruing graph %s' % graph.name)
    points_q_template = PointModel.query(PointModel.graph == graph.key)
    now = datetime.datetime.utcnow()  # Pin the time.
    for td_ago, td_window in PRUNE_CONFIG:
      # Seed the initial window, snap to td_window.
      time_end = (now - td_ago + td_window)
      offset = datetime.timedelta(seconds=(time_end -
                                           datetime.datetime(2000,
                                                             1,
                                                             1)).total_seconds()
                                          % td_window.seconds)
      time_end -= offset

      while True:
        time_end -= td_window
        time_start = time_end - td_window
        points_q = points_q_template.filter(PointModel.timestamp < time_end)
        points_q = points_q.filter(PointModel.timestamp >= time_start)
        points_q = points_q.order(-PointModel.timestamp)
        points = points_q.fetch()
        if not points:
          break
        if len(points) == 1:
          continue

        # We're going to derive the value types out of this point, and also
        # collapse the other points into this point.
        key_point = points[0]
        value_lists = dict([(value_name, [])
                            for value_name in key_point.values])

        for point in points:
          for value_name, value_list in value_lists.items():
            if value_name in point.values:
              value_list.append(point.values[value_name])

        new_values = dict([
            (value_name, float(sum(value_list))/float(len(value_list)))
            for value_name, value_list in value_lists.iteritems()])
        key_point.values = new_values
        key_point.timestamp = time_start
        key_point.put_async()

        # Now actually prune this point.
        for point in points[1:]:
          point.key.delete_async()


  def post(self, graph_name):
    self.get(graph_name)


class UpdateAll(webapp2.RequestHandler):
  def get(self):
    """Update all builders, masters, and build info entries.

    This can be seen as the entry point for the app.  All tasks are orginated
    from here.
    """
    for master in DEFAULT_MASTER:
      # Populate the build queue graphs for each master.
      url = '/tasks/update_build_queue/%s' %  master
      logging.debug('Adding %s' % url)
      taskqueue.add(url=url)

    # Update CQ statistics.
    taskqueue.add(url='/tasks/update_cq')


class UpdatePrune(webapp2.RequestHandler):
  def get(self):
    """Update graph pruning jobs."""
    for graph in GraphModel.query().fetch():
      for tag in graph.tags:
        if tag in WHITELIST_FOR_PRUNING:
          url = '/tasks/prune_graph/%s' % graph.key.id()
          logging.debug('Adding %s' % url)
          taskqueue.add(url=url, queue_name='graphs')
          break


app = webapp2.WSGIApplication([
    ('/tasks/update_all', UpdateAll),
    ('/tasks/update_prune', UpdatePrune),

    ('/tasks/update_cq', UpdateCQ),
    ('/tasks/prune_graph/(.+)', PruneGraph),

    ('/tasks/update_build_queue/(.+)', UpdateBuildQueue),
    ('/tasks/update_builder_success_rate/(.+)/(.+)/(.+)',
     UpdateBuilderSuccessRate),
    ('/tasks/update_builder_times/(.+)/(.+)/(.+)', UpdateBuilderTimes),
    ('/view_graph/(.+)', ViewGraph),
    ('/list_graphs/(.+)/?', ListGraphs),
    ('/list_graphs/?', ListGraphs),
    ('/', ListGraphs),
])
