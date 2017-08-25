# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import hashlib
import urllib

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.ext import ndb
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import auth
from components import net
from components import utils
import gae_ts_mon
import endpoints

from . import swarming
import acl
import api
import config
import errors


def swarmbucket_api_method(
    request_message_class, response_message_class, **kwargs):
  """Defines a swarmbucket API method."""

  endpoints_decorator = auth.endpoints_method(
      request_message_class, response_message_class, **kwargs)

  def decorator(fn):
    fn = auth.public(fn)
    fn = endpoints_decorator(fn)
    fn = ndb.toplevel(fn)
    def ts_mon_time():
      return utils.datetime_to_timestamp(utils.utcnow()) / 1000000.0
    fn = gae_ts_mon.instrument_endpoint(time_fn=ts_mon_time)(fn)
    return fn

  return decorator


class BuilderMessage(messages.Message):
  name = messages.StringField(1)
  category = messages.StringField(2)


class BucketMessage(messages.Message):
  # Bucket name. Unique per buildbucket instance.
  name = messages.StringField(1)
  builders = messages.MessageField(BuilderMessage, 2, repeated=True)


class GetBuildersResponseMessage(messages.Message):
  buckets = messages.MessageField(BucketMessage, 1, repeated=True)


class GetTaskDefinitionRequestMessage(messages.Message):
  # A build creation request. Buildbucket will not create the build and won't
  # allocate a build number, but will return a definition of the swarming task
  # that would be created for the build. Build id will be 1 and build number (if
  # configured) will be 0.
  build_request = messages.MessageField(api.PutRequestMessage, 1, required=True)
  # if True (default), an API Explorer link is returned.
  # See GetTaskDefinitionResponseMessage for details.
  api_explorer_link = messages.BooleanField(2)


class GetTaskDefinitionResponseMessage(messages.Message):
  # A definition of the swarming task that would be created for the specified
  # build.
  task_definition = messages.StringField(1)
  # An API Explorer link to Swarming's tasks.new API
  # with the pre-filled request body.
  api_explorer_link = messages.StringField(3)


@auth.endpoints_api(
  name='swarmbucket', version='v1',
  title='Buildbucket-Swarming integration')
class SwarmbucketApi(remote.Service):
  """API specific to swarmbucket."""

  @swarmbucket_api_method(
      message_types.VoidMessage,
      GetBuildersResponseMessage,
      path='builders', http_method='GET')
  def get_builders(self, _request):
    """Returns defined swarmbucket builders.

    Can be used by code review tool to discover builders.
    """
    buckets = config.get_buckets_async().get_result()
    available = acl.get_available_buckets()
    if available is not None:  # pragma: no branch
      available = set(available)
      buckets = [b for b in buckets if b.name in available]

    res = GetBuildersResponseMessage()
    for bucket in buckets:
      if not bucket.swarming.builders:
        continue
      res.buckets.append(BucketMessage(
        name=bucket.name,
        builders=[
          BuilderMessage(
            name=builder.name,
            category=builder.category,
          )
          for builder in bucket.swarming.builders
        ],
      ))
    return res

  @swarmbucket_api_method(
      GetTaskDefinitionRequestMessage,
      GetTaskDefinitionResponseMessage)
  def get_task_def(self, request):
    """Returns a swarming task definition for a build request."""
    try:
      build_request = api.put_request_message_to_build_request(
          request.build_request)
      build_request = build_request.normalize()

      identity = auth.get_current_identity()
      if not acl.can_view_build(build_request):
        raise endpoints.ForbiddenException(
            '%s cannot view builds in bucket %s' %
            (identity, build_request.bucket))

      build = build_request.create_build(1, identity, utils.utcnow())
      bucket_cfg, _, task_def = (
          swarming.prepare_task_def_async(build, fake_build=True).get_result())
      task_def_json = json.dumps(task_def)

      res = GetTaskDefinitionResponseMessage(task_definition=task_def_json)
      if request.api_explorer_link != False:  # pragma: no branch
        res.api_explorer_link = shorten_url(
            ('https://%s/_ah/api/explorer'
             '#p/swarming/v1/swarming.tasks.new?resource=%s') %
            (bucket_cfg.swarming.hostname, urllib.quote(task_def_json)))
      return res
    except errors.InvalidInputError as ex:
      raise endpoints.BadRequestException(
          'invalid build request: %s' % ex.message)


def shorten_url(long_url):
  link_hash = hashlib.sha256(long_url).hexdigest()
  cache_key = 'shortlink/' + link_hash
  short_url = memcache.get(cache_key)
  if not short_url:
    res = net.json_request(
        url='https://www.googleapis.com/urlshortener/v1/url',
        method='POST',
        payload={'longUrl': long_url},
        scopes='https://www.googleapis.com/auth/urlshortener',
    )
    short_url = res['id']
    memcache.set(cache_key, short_url)
  return short_url
