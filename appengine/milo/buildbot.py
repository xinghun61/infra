# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Cloud Endpoints for Buildbot Endpoints.

This provides an appengine caching layer for buildbot endpoints.
"""

import json
import endpoints
import os
import sys
import webapp2
import urllib
import logging

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from google.appengine.ext import ndb
from google.appengine.api import memcache
from google.appengine.api import urlfetch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

from components import ereporter2
from components import utils
from components import auth

VERSION_ID = os.environ['CURRENT_VERSION_ID']

##########
# Models #
##########
class BuildbotJsonCache(ndb.Model):
  """Datastore cache of a buildbot build Json."""
  master = ndb.StringProperty()
  builder = ndb.StringProperty()
  build = ndb.IntegerProperty()
  data = ndb.JsonProperty(compressed=True)
  created = ndb.DateTimeProperty(auto_now_add=True)
  modified = ndb.DateTimeProperty(auto_now=True)


#########
# Pages #
#########

class FrontPage(webapp2.RequestHandler):
  def get(self):
    """Redirect to the Chromium Project view."""
    self.redirect('/projects/chromium')


class MastersListPage(webapp2.RequestHandler):
  def get(self):
    pass


class MasterPage(webapp2.RequestHandler):
  def get(self, master):
    pass


class BuildersListPage(webapp2.RequestHandler):
  def get(self):
    pass


class BuilderPage(webapp2.RequestHandler):
  def get(self):
    pass


class BuildRequest(messages.Message):
  """Request for a buildbot build query."""
  master = messages.StringField(1, required=True)
  builder = messages.StringField(2, required=True)
  build = messages.IntegerField(3, required=True)


class MiloItem(messages.Message):
  main_text = messages.StringField(1, required=True)
  status = messages.StringField(2)
  right_text = messages.StringField(3)
  sub_text = messages.StringField(4)


class MiloResponse(messages.Message):
  name = messages.StringField(1, required=True)
  status = messages.StringField(2)
  topbar = messages.MessageField(MiloItem, 5, repeated=True)
  content = messages.MessageField(MiloItem, 6, repeated=True)
  properties = messages.MessageField(MiloItem, 7, repeated=True)


class StepResponse(messages.Message):
  name = messages.StringField(1, required=True)
  status = messages.StringField(2, required=True)


class BuildNotFound(Exception):
  pass


@auth.endpoints_api(
    name='buildbot',
    version='v1',
    title='Milo Buildbot API')
class BuildbotApi(remote.Service):
  def _get_build(self, master, builder, build):
    """Try to return the build json from the cache, or otherwise fetch it."""
    # 1. Try memcache.
    memcache_key = '%s:build:%s:%s:%s' % (VERSION_ID, master, builder, build)
    data = memcache.get(memcache_key)
    if data:
      return data

    # 2. Try the datastore.
    db_results = BuildbotJsonCache.query(
        BuildbotJsonCache.master == master,
        BuildbotJsonCache.builder == builder,
        BuildbotJsonCache.build == build).fetch(1)
    if db_results:
      data = db_results[0].data
      memcache.set(memcache_key, json.dumps(data))
      return data

    # 3. Try CBE.
    cbe_url = (
        'chrome-build-extract.appspot.com/p/%s/builders/%s/builds/%s'
        % (master, builder, build))
    full_cbe_url = 'https://%s' % urllib.quote(cbe_url)
    cbe_response = urlfetch.fetch(full_cbe_url)
    if cbe_response.status_code == 200:
      data = json.loads(cbe_response.content)
    else:
      # 4. Fetch it from buildbot.
      buildbot_url = (
          'build.chromium.org/p/%s/json/builders/%s/builds/%s'
          % (master, builder, build))
      full_buildbot_url = 'https://%s' % urllib.quote(buildbot_url)
      bb_response = urlfetch.fetch(full_buildbot_url)
      if bb_response.status_code != 200:
        logging.exception(
            'Buildbot returned %d while fetching %s' %
            (bb_response.status_code, full_buildbot_url))
        raise BuildNotFound()
      data = json.loads(bb_response.content)

    # Cache build if its complete.
    if not data['currentStep']:
      json_cache = BuildbotJsonCache(
          master=master, builder=builder, build=build, data=data)
      json_cache.put()
      memcache.set(memcache_key, data)

    return data

  @staticmethod
  def get_topbar(data):
    if not data['times'][1]:
      return MiloItem(main_text='Running', status='running')
    elif not data.get('results'):
      # If results == 0 the key might not show up in the json, because buildbot.
      return MiloItem(
        main_text='This build passed successfully! :D',
        status='success')
    return MiloItem(main_text='Failure', status='failure')

  @staticmethod
  def get_step(data):
    pass

  @staticmethod
  def get_steps(data):
    return [BuildbotApi.get_step(step) for step in data['steps']]

  @auth.endpoints_method(
      BuildRequest,
      MiloResponse,
      path='buildbot/{master}/builders/{builder}/builds/{build}',
      http_method='GET',
      name='getBuild')
  def build(self, request):
    data = self._get_build(request.master, request.builder, request.build)
    topbar = self.get_topbar(data)
    name = '%s - %d' % (request.builder, request.build)
    root = MiloResponse(name=name, topbar=[topbar])
    return root
