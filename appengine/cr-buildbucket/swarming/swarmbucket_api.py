# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import auth
from components import utils
import gae_ts_mon

import acl
import config


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
