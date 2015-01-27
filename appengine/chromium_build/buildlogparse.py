# buildlogparse.py: Proxy and rendering layer for build.chromium.org.
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import jinja2
import json
import logging
import os
import re
import time
import urllib
import urlparse
import webapp2
import zlib

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

import utils


VERSION_ID = os.environ['CURRENT_VERSION_ID']

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                   'templates')),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])
jinja_environment.filters['delta_time'] = utils.delta_time
jinja_environment.filters['nl2br'] = utils.nl2br
jinja_environment.filters['time_since'] = utils.time_since
jinja_environment.filters['rot13_email'] = utils.rot13_email
jinja_environment.filters['cl_comment'] = utils.cl_comment

if os.environ.get('HTTP_HOST'):
  APP_URL = os.environ['HTTP_HOST']
else:
  APP_URL = os.environ['SERVER_NAME']

# Note: All of these replacements occur AFTER jinja autoescape.
# This way we can add <html> tags in the replacements, but do note that spaces
# are &nbsp;.
REPLACEMENTS = [
    # Find ../../scripts/.../*.py scripts and add links to them.
    (r'\.\./\.\./\.\./scripts/(.*)\.py',
     r'<a href="https://code.google.com/p/chromium/codesearch#chromium/tools/'
     r'build/scripts/\1.py">../../scripts/\1.py</a>'),

    # Find ../../chrome/.../*.cc files and add links to them.
    (r'\.\./\.\./chrome/(.*)\.cc:(\d+)',
     r'<a href="https://code.google.com/p/chromium/codesearch#chromium/src/'
     r'chrome/\1.cc&l=\2">../../chrome/\1.cc:\2</a>'),

    # Searches for codereview issue numbers, and add codereview links.
    (r'apply_issue(.*)-i&nbsp;(\d{8})(.*)-s&nbsp;(.*)',
     r'apply_issue\1-i&nbsp;<a href="\4/\2">\2</a>\3-s&nbsp;\4'),

    # Add green labels to PASSED or OK items.
    (r'\[((&nbsp;&nbsp;PASSED&nbsp;&nbsp;)|'
     r'(&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;OK&nbsp;))\]',
     r'<span class="label label-success">[\1]</span>'),

    # Add red labels to FAILED items.
    (r'\[(&nbsp;&nbsp;FAILED&nbsp;&nbsp;)\]',
     r'<span class="label label-important">[\1]</span>'),

    # Add black labels ot RUN items.
    (r'\[(&nbsp;RUN&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)\]',
     r'<span class="label label-inverse">[\1]</span>'),

    # Add badges to running tests.
    (r'\[((&nbsp;)*\d+/\d+)\]((&nbsp;)+)(\d+\.\d+s)&nbsp;'
     r'([\w/]+\.[\w/]+)&nbsp;\(([\d.s]+)\)',
     r'<span class="badge badge-success">\1</span>\3<span class="badge">'
     r'\5</span>&nbsp;\6&nbsp;<span class="badge">\7</span>'),

    # Add gray labels to [==========] blocks.
    (r'\[([-=]{10})\]',
     r'<span class="label">[\1]</span>'),

    # Find .cc and .h files and add codesite links to them.
    (r'\.\./\.\./([\w/-]+)\.(cc|h):&nbsp;',
     r'<a href="https://code.google.com/p/chromium/codesearch#chromium/src/'
     r'\1.\2">../../\1.\2</a>:&nbsp;'),

    # Find source files with line numbers and add links to them.
    (r'\.\./\.\./([\w/-]+)\.(cc|h):(\d+):&nbsp;',
     r'<a href="https://code.google.com/p/chromium/codesearch#chromium/src/'
     r'\1.\2&l=\3">../../\1.\2:\3</a>:&nbsp;'),

    # Add badges to compiling items.
    (r'\[(\d+/\d+)\]&nbsp;(CXX|AR|STAMP|CC|ACTION|RULE|COPY)',
     r'<span class="badge badge-info">\1</span>&nbsp;'
     r'<span class="badge">\2</span>'),

    # Bold the LHS of A=B text.
    (r'^((&nbsp;)*)(\w+)=([\w:/-_.]+)',
     r'\1<strong>\3</strong>=\4'),
]


########
# Models
########
class BuildLogModel(ndb.Model):
  # Used for caching finished build logs.
  url = ndb.StringProperty()
  data = ndb.BlobProperty()

class BuildbotCacheModel(ndb.Model):
  # Used for caching finished build data.
  url = ndb.StringProperty()
  data = ndb.BlobProperty()

class BuildLogResultModel(ndb.Model):
  # Used for caching finished and parsed build logs.
  url = ndb.StringProperty()
  version = ndb.StringProperty()
  data = ndb.BlobProperty()


def emit(source, out):
  # TODO(hinoka): This currently employs a "lookback" strategy
  # (Find [PASS/FAIL], then goes back and marks all of the lines.)
  # This should be switched to a "scan twice" strategy.  1st pass creates a
  # Test Name -> PASS/FAIL/INCOMPLETE dictionary, and 2nd pass marks the lines.
  attr = []
  if source == 'header':
    attr.append('text-info')
  lines = []
  current_test = None
  current_test_line = 0
  for line in out.split('\n'):
    if line:
      test_match = re.search(r'\[ RUN      \]\s*([^() ]*)\s*', line)
      line_attr = attr[:]
      if test_match:
        # This line is a "We're running a test" line.
        current_test = test_match.group(1).strip()
        current_test_line = len(lines)
      elif '[       OK ]' in line or '[  PASSED  ]' in line:
        line_attr.append('text-success')
        test_match = re.search(r'\[       OK \]\s*([^(), ]*)\s*', line)
        if test_match:
          finished_test = test_match.group(1).strip()
          for line_item in lines[current_test_line:]:
            if finished_test == current_test:
              line_item[2].append('text-success')
            else:
              line_item[2].append('text-error')
        current_test = None
      elif '[  FAILED  ]' in line:
        line_attr.append('text-error')
        test_match = re.search(r'\[  FAILED  \]\s*([^(), ]*)\s*', line)
        if test_match:
          finished_test = test_match.group(1).strip()
          for line_item in lines[current_test_line:]:
            if finished_test == current_test:
              line_item[2].append('text-error')
        current_test = None
      elif re.search(r'\[.{10}\]', line):
        current_test = None
      elif re.search(r'\[\s*\d+/\d+\]\s*\d+\.\d+s\s+[\w/]+\.'
                     r'[\w/]+\s+\([\d.s]+\)', line):
        # runtest.py output: [20/200] 23.3s [TestSuite.TestName] (5.3s)
        current_test = None
        line_attr.append('text-success')
      elif 'aborting test' in line:
        current_test = None
      elif current_test:
        line_attr.append('text-warning')

      line = line.replace(' ', '&nbsp;')
      for rep_from, rep_to in REPLACEMENTS:
        line = re.sub(rep_from, rep_to, line)
      lines.append((line, line_attr))
  return (source, lines)


class BuildbotPassthrough(webapp2.RequestHandler):
  def get(self, path):
    # TODO(hinoka): Page caching.
    url = 'build.chromium.org/p/%s' % path
    full_url = 'https://%s' % urllib.quote(url)
    s = urlfetch.fetch(full_url, method=urlfetch.GET, deadline=60).content
    s = s.replace('default.css', '../../static/default-old.css')
    self.response.out.write(s)


class Build(webapp2.RequestHandler):
  @staticmethod
  @ndb.toplevel
  def get_build_step(master, builder, step):
    data = get_build(master, builder, step).get_result()
    return data

  @utils.render_iff_new_flag_set('step.html', jinja_environment)
  def get(self, master, builder, step, new=None):
    """Parses a build step page."""
    # Fetch the page.
    if new:
      result = Build.get_build_step(master, builder, step)
      if not result:
        self.error(404)
        return

      # Add on some extraneous info.
      build_properties = dict((name, value) for name, value, _
                              in result['properties'])
      failed_steps = ['<strong>%s</strong>' % s['name'] for s in result['steps']
                      if s['results'][0] == 2]
      if len(failed_steps) == 1:
        result['failed_steps'] = failed_steps[0]
      elif len(failed_steps) == 2:
        logging.info(failed_steps)
        result['failed_steps'] = '%s and %s' % tuple(failed_steps)
      elif failed_steps:
        # Oxford comma.
        result['failed_steps'] = '%s, and %s' % (
            ', '.join(failed_steps[:-1], failed_steps[-1]))
      else:
        result['failed_steps'] = None

      if 'rietveld' in build_properties:
        result['rietveld'] = build_properties['rietveld']
      result['breadcrumbs'] = [
          ('Master %s' % master, '/buildbot/%s' % master),
          ('Builder %s' % builder, '/buildbot/%s/builders/%s' %
              (master, builder)),
          ('Slave %s' % result['slave'],
              '/buildbot/%s/buildslaves/%s' % (master, result['slave'])),
          ('Build Number %s' % step,
              '/buildbot/%s/builders/%s/builds/%s' %
              (master, builder, step)),
      ]
      result['url'] = self.request.url.split('?')[0]
      return result
    else:
      url = ('http://build.chromium.org/p/%s/'
          'builders/%s/builds/%s' % (master, builder, step))
      s = urlfetch.fetch(url.replace(' ', '%20'),
          method=urlfetch.GET, deadline=60).content
      s = s.replace('../../../default.css', '/static/default-old.css')
      s = s.replace('<a href="../../../about">About</a>',
        '<a href="../../../about">About</a>'
        ' - <a href="%s?new=true">New Layout</a>' %
        self.request.url.split('?')[0])
      return s


@ndb.tasklet
def get_build(master, builder, build):
  # Get build from:
  # 1. Memcache
  # 2. Local datastore
  # 3. Chrome build extract cache
  # 4. Original buildbot master
  ctx = ndb.get_context()

  # 1. Try the local memcache.
  url = ('https://build.chromium.org/p/%s/json/builders/%s/builds/%s' %
         tuple(map(urllib.quote, (master, builder, str(build)))))
  key = '%s:build:%s' % (VERSION_ID, url)
  data = yield ctx.memcache_get(key)
  if data:
    logging.debug('Fetched %s from memcache.' % url)
    raise ndb.Return(json.loads(data))

  # 2. Try the local datastore.
  result = yield BuildbotCacheModel.query(
      BuildbotCacheModel.url == url).fetch_async(1)
  if result:
    data = result[0].data
    try:
      json_data = json.loads(data)
    except Exception:
      logging.warning('Invalid json from datastore: %s\n' % data)
      result[0].key.delete()  # Invalid data
    else:
      ctx.memcache_set(key, data)
      logging.debug('Fetched %s from datastore.' % url)
      raise ndb.Return(json_data)

  # 3. Try CBE.
  cbe_url = (
      'https://chrome-build-extract.appspot.com/p/%s/builders/%s/builds/%s'
      % tuple(map(urllib.quote, (master, builder, str(build)))))
  response = yield ctx.urlfetch(cbe_url)
  if response.status_code != 200:
    # 4. Just fetch it from buildbot.
    response = yield ctx.urlfetch(url)
    if response.status_code != 200:
      logging.error(
          'Fetching %s returned error %d' % (url, response.status_code))
      raise ndb.Return(None)
    logging.debug('Fetched %s' % url)
  else:
    logging.debug('Fetched %s from CBE' % cbe_url)
  data = response.content
  json_data = json.loads(data)

  if not json_data['currentStep']:
    build_cache = BuildbotCacheModel(url=url, data=data)
    build_cache.put_async()
    ctx.memcache_set(key, data)
  raise ndb.Return(json_data)


class BuildSlave(webapp2.RequestHandler):
  """Parses a build slave page."""
  @staticmethod
  @ndb.toplevel
  def get_recent_builds(master, builders, limit=10):
    if not builders:
      return []
    # Build job list consisting of urls.
    jobs = []
    for builder, builds in builders.iteritems():
      builds = sorted(builds, reverse=True)
      if len(builds) > limit:
        builds = builds[:limit]
      for build in builds:
        jobs.append(get_build(master, builder, build))

    builds = [build.get_result() for build in jobs]
    builds = [build for build in builds if build]
    return sorted(builds, key=lambda x: x['times'][1], reverse=True)

  @staticmethod
  def get_slave_json(master, slave):
      json_url = ('https://build.chromium.org/p/%s/'
          'json/slaves/%s' % tuple(map(urllib.quote, (master, slave))))
      memcache_key = '%s:url:%s' % (VERSION_ID, json_url)
      s = memcache.get(memcache_key)
      if not s:
        s = urlfetch.fetch(json_url, method=urlfetch.GET, deadline=60).content
        memcache.set(memcache_key, s, time=60)
        logging.info('Loaded %s' % json_url)
      else:
        logging.info('Loaded %s from memcache' % json_url)
      return json.loads(s)


  @utils.render_iff_new_flag_set('slave.html', jinja_environment)
  def get(self, master, slave, new=None):
    # Fetch the page.
    if new:
      result = self.get_slave_json(master, slave)
      builders = result.get('builders', {})
      result['recent_builds'] = self.get_recent_builds(master, builders)
      result['breadcrumbs'] = [
          ('Master %s' % master,
           '/buildbot/%s?new=true' % master),
          ('All Slaves',
           '/buildbot/%s/buildslaves?new=true' % master),
          ('Slave %s' % slave,
           '/buildbot/%s/buildslaves/%s?new=true' % (master, slave)),
      ]
      result['url'] = self.request.url.split('?')[0]
      result['master'] = master
      result['slave'] = slave
      return result
    else:
      url = ('http://build.chromium.org/p/%s/buildslaves/%s' %
             tuple(map(urllib.quote, (master, slave))))
      s = urlfetch.fetch(url, method=urlfetch.GET, deadline=60).content
      s = s.replace('../default.css', '/static/default-old.css')
      s = s.replace('<a href="../about">About</a>',
        '<a href="../about">About</a>'
        ' - <a href="%s?new=true">New Layout</a>' %
        self.request.url.split('?')[0])
      return s


class MainPage(webapp2.RequestHandler):
  """Parses a buildlog page."""
  @utils.render('buildbot.html', jinja_environment)
  @utils.expect_request_param('url')
  def get(self, url):
    if not url:
      return {}

    # Redirect the page if we detect a different type of URL.
    _, _, path, _, _, _ = urlparse.urlparse(url)
    logging.info(path)
    step_m = re.match(r'^/((p/)?)(.*)/builders/(.*)/builds/(\d+)$', path)
    if step_m:
      self.redirect('/buildbot/%s/builders/%s/builds/%s' % step_m.groups()[2:])
      return {}

    log_m = re.match(
        r'^/((p/)?)(.*)/builders/(.*)/builds/(\d+)/steps/(.*)/logs/(.*)', path)
    if log_m:
      self.redirect('/buildbot/%s/builders/%s/builds/%s/steps/%s'
          '/logs/%s?new=true' % log_m.groups()[2:])
      return {}

    self.error(404)
    return {'error': 'Url not found: %s' % url}

class BuildLog(webapp2.RequestHandler):
  @staticmethod
  def fetch_buildlog(url):
    """Fetch buildlog from either the datastore cache or the remote url.
    Caches the log once fetched."""
    buildlog = BuildLogModel.all().filter('url =', url).get()
    if buildlog:
      return zlib.decompress(buildlog.data)
    else:
      log_fetch_start = time.time()
      s = urlfetch.fetch(url.replace(' ', '%20'),
          method=urlfetch.GET, deadline=60).content
      logging.info('Log fetching time: %2f' % (time.time() - log_fetch_start))
      # Cache this build log.
      # TODO(hinoka): This should be in Google Storage.
      compressed_data = zlib.compress(s)
      if len(compressed_data) < 10**6:
        buildlog = BuildLogModel(url=url, data=compressed_data)
        buildlog.put()
      return s

  @utils.render_iff_new_flag_set('logs.html', jinja_environment)
  def get(self, master, builder, build, step, logname, new):
    # Lets fetch the build data first to determine if this is a running step.
    build_data = Build.get_build_step(master, builder, build)
    steps = dict([(_step['name'], _step) for _step in build_data['steps']])
    # Construct the url to the log file.
    url = ('http://build.chromium.org/'
           'p/%s/builders/%s/builds/%s/steps/%s/logs/%s' %
           (master, builder, build, step, logname))
    current_step = steps[step]
    if not current_step['isFinished']:
      # We're not finished with this step, redirect over to the real buildbot.
      self.redirect(url)
      return {}  # Empty dict to keep the decorator happy.

    if new:
      logging.info('New layout')
      # New layout: We want to fetch the processed json blob.
      # Check for cached results or fetch the page if none exists.
      cached_result = BuildLogResultModel.all().filter(
            'url =', url).filter('version =', VERSION_ID).get()
      if cached_result:
        logging.info('Returning cached data')
        return json.loads(zlib.decompress(cached_result.data))
      else:
        # Fetch the log from the buildbot master.
        s = BuildLog.fetch_buildlog(url)

        # Parse the log output to add colors.
        parse_time_start = time.time()
        all_output = re.findall(r'<span class="(header|stdout)">(.*?)</span>',
                                s, re.S)
        result_output = []
        current_source = None
        current_string = ''
        for source, output in all_output:
          if source == current_source:
            current_string += output
            continue
          else:
            # We hit a new source, we want to emit whatever we had left and
            # start anew.
            if current_string:
              result_output.append(emit(current_source, current_string))
            current_string = output
            current_source = source
        if current_string:
          result_output.append(emit(current_source, current_string))
        logging.info('Parse time: %2f' % (time.time() - parse_time_start))

        # Add build PASS/FAIL banner.
        ret_code_m = re.search('program finished with exit code (-?\d+)', s)
        if ret_code_m:
          ret_code = int(ret_code_m.group(1))
          if ret_code == 0:
            status = 'OK'
          else:
            status = 'ERROR'
        else:
          ret_code = None
          status = None

        final_result = {
            'output': result_output,
            'org_url': url,
            'url': self.request.url.split('?')[0],
            'name': step,
            'breadcrumbs': [
                ('Master %s' % master,
                    '/buildbot/%s/waterfall' % master),
                ('Builder %s' % builder,
                    '/buildbot/%s/builders/%s' %
                    (master, builder)),
                ('Slave %s' % build_data['slave'],
                    '/buildbot/%s/buildslaves/%s' %
                    (master, build_data['slave'])),
                ('Build Number %s ' % build,
                    '/buildbot/%s/builders/%s/builds/%s' %
                    (master, builder, build)),
                ('Step %s' % step, '/buildbot/%s/builders/%s/builds/%s'
                    '/steps/%s/logs/%s' %
                    (master, builder, build, step, logname))
            ],
            'status': status,
            'ret_code': ret_code,
            'debug': self.request.get('debug'),
            'size': len(s),
            'slave': build_data['slave']
        }
        # Cache parsed logs.
        # TODO(hinoka): This should be in Google storage, where the grass is
        #               green and size limits don't exist.
        compressed_result = zlib.compress(json.dumps(final_result))
        if len(compressed_result) < 10**6:
          cached_result = BuildLogResultModel(
              url=url, version=VERSION_ID, data=compressed_result)
          cached_result.put()

        return final_result
    else:
      # Fetch the log from the buildbot master.
      logging.info('Old layout')
      s = BuildLog.fetch_buildlog(url)
      s = s.replace('default.css', '../../static/default-old.css')
      s = s.replace('<a href="stdio/text">(view as text)</a>',
          '<a href="stdio/text">(view as text)</a><br/><br/>'
          '<a href="%s?new=true">(New layout)</a>' %
          self.request.url.split('?')[0])
      return s


app = webapp2.WSGIApplication([
    ('/buildbot/', MainPage),
    ('/buildbot/(.*)/builders/(.*)/builds/(\d+)/steps/(.*)/logs/(.*)/?',
        BuildLog),
    ('/buildbot/(.*)/builders/(.*)/builds/(\d+)/?', Build),
    ('/buildbot/(.*)/buildslaves/(.*)/?', BuildSlave),
    ('/buildbot/(.*)', BuildbotPassthrough),
    ])
