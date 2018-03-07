# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implements fetching of build steps from LogDog."""

import base64
import logging
import urlparse

from google.appengine.ext import ndb

from components import net

from . import annotations
from . import errors
from third_party import annotations_pb2


@ndb.tasklet
def fetch_steps_async(build, allowed_logdog_hosts):
  """Fetches steps of a model.Build and returns them in step_pb2.Step format.

  Returns:
    A tuple (steps, finalized) where
    - steps is list of step_pb2.Step messages
    - finalized is True if the returned steps are finalized, otherwise False.

  Raises:
    errors.UnsupportedBuild: build has no anontation log URL or
      the logdog host is not allowed.
    errors.MalformedBuild: failed to retrieve/parse logdog annotation URL.
    errors.StepFetchError: failed to fetch steps.
  """
  # Both LUCI and Buildbot builds have steps in "annotations"
  # LogDog stream, so we can have same implementation for both.

  logdog_url = _get_annotation_url(build)
  if not logdog_url:
    raise errors.MalformedBuild(
        'build %d does not have log location' % build.key.id())
  try:
    host, project, prefix, stream_name = _parse_logdog_url(logdog_url)
  except ValueError:
    raise errors.MalformedBuild(
        'invalid LogDog URL %r in build %d' % (logdog_url, build.key.id()))

  if host not in allowed_logdog_hosts:
    msg = (
        'build %d references LogDog host %s that is not allowed' %
        (build.key.id(), host))
    logging.error(msg)
    raise ndb.Return([], True)

  try:
    res = yield net.json_request_async(
        url='https://%s/prpc/logdog.Logs/Tail' % host,
        method='POST',
        scopes=net.EMAIL_SCOPE,
        payload={
          'project': project,
          'path': '%s/+/%s' % (prefix, stream_name),
          'state': True,
        },
    )
  except net.NotFoundError:
    # This stream wasn't even registered.
    # It should have been registered in the beginning of the build.
    logging.warning('logdog stream does not exist: %s', logdog_url)
    raise ndb.Return([], False)
  except net.Error as ex:
    # This includes auth errors.
    logging.exception('failed to fetch steps for build %d', build.key.id())
    raise errors.StepFetchError('failed to fetch steps: %s' % ex.message)

  log = res['logs'][0]
  ann_step = annotations_pb2.Step()
  ann_step.ParseFromString(base64.b64decode(log['datagram']['data']))
  converter = annotations.Converter(
      default_logdog_host=host,
      default_logdog_prefix='%s/%s' % (project, prefix),
  )

  terminal_index = int(res['state']['terminalIndex'])
  raise ndb.Return(
    converter.parse_substeps(ann_step.substep),
    terminal_index != 1 and int(log['sequence']) == terminal_index,
  )


def _get_annotation_url(build):
  """Returns a LogDog URL of the annotations datagram stream."""

  # Buildbot builds have log_location in properties.
  result_details = build.result_details or {}
  annotation_url = result_details.get('properties', {}).get('log_location')
  if annotation_url:
    return annotation_url

  # LUCI builds have the logdog URL in tags.
  prefix = 'swarming_tag:log_location:'
  for t in build.tags:
    if t.startswith(prefix):
      return t[len(prefix):]

  return None


def _parse_logdog_url(url):
  # LogDog URL example:
  #   'logdog://logs.chromium.org/chromium/'
  #   'buildbucket/cr-buildbucket.appspot.com/8953190917205316816/+/annotations'
  u = urlparse.urlparse(url)
  full_path = u.path.strip('/').split('/')
  if (u.scheme != 'logdog' or u.params or u.query or u.fragment or
      len(full_path) < 4 or '+' not in full_path):
    raise ValueError('invalid logdog URL %r' % url)
  project = full_path[0]
  plus_pos = full_path.index('+')
  stream_prefix = '/'.join(full_path[1:plus_pos])
  stream_name = '/'.join(full_path[plus_pos+1:])
  return u.netloc, project, stream_prefix, stream_name
