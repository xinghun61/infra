# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A minimal isolate client that uses components.net for network IO."""

import base64
import collections
import zlib

from google.appengine.ext import ndb

from components import net


class Error(Exception):
  """An isolated file could not be fetched."""


LocationBase = collections.namedtuple(
    'LocationBase', 'hostname namespace digest')


class Location(LocationBase):
  """Location of a file on an isolate server."""

  def __init__(self, hostname, namespace, digest):
    assert not hostname.startswith(('https://', 'http://')), hostname
    super(Location, self).__init__(hostname, namespace, digest)

  @property
  def human_url(self):
    return 'https://%s/browse?namespace=%s&digest=%s' % self


@ndb.tasklet
def fetch_async(loc):
  """Fetches file contents from an isolate server.

  Assumes that files are compressed with zlib.

  Warning: will buffer entire file in process memory.
  Do not call for large files.
  """
  try:
    res = yield net.json_request_async(
        'https://%s/_ah/api/isolateservice/v1/retrieve' % loc.hostname,
        method='POST',
        payload={
          'digest': loc.digest,
          'namespace': {'namespace': loc.namespace},
        },
        scopes=net.EMAIL_SCOPE,
    )
  except net.Error as ex:
    raise Error(
        'Could not fetch %s: %s' % (loc.human_url, ex))

  if 'content' in res:
    try:
      content = base64.b64decode(res['content'])
    except TypeError as ex:
       raise Error('could parse response for %s: %s' % (loc.human_url, ex))
  elif 'url' in res:
    try:
      content = yield net.request_async(res['url'])
    except net.Error as ex:
      raise Error(
          'Could not fetch %s from %s: %s' % (loc.human_url, res['url'], ex))
  else:
    raise Error('expected url or content in isolateserver.retrieve response')

  del res

  try:
    raise ndb.Return(zlib.decompress(content))
  except zlib.error as ex:
    raise Error('Could not decompress contents of %s: %s' % (loc.human_url, ex))
