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


def fetch_steps_async(build, allowed_logdog_hosts):
  """Fetches steps of a model.Build and returns them in step_pb2.Step format.

  If the build is not a swarmbucket build, returns ([], True).

  Returns:
    A tuple (steps, finalized) where
    - steps is list of step_pb2.Step messages
    - finalized is True if the returned steps are finalized, otherwise False.

  Raises:
    errors.MalformedBuild: failed to retrieve/parse logdog annotation URL.
    errors.StepFetchError: failed to fetch steps.
  """
  if not build.swarming_task_id:
    # This is not a swarmbucket build.
    # Not all Buildbot builds have annotation URL.
    # Among those that do, not all have valid annotations, i.e. some of them are
    # not valid annotation protos.
    f = ndb.Future()
    f.set_result(([], True))
    return f

  return fetch_steps_from_logdog_async(
      build.key.id(), _get_annotation_url(build), allowed_logdog_hosts)


@ndb.tasklet
def fetch_steps_from_logdog_async(
    build_id, annotation_url, allowed_logdog_hosts):
  """Fetches steps from LogDog and returns them in step_pb2.Step format.

  build_id is used only for logging.

  Returns:
    A tuple (steps, finalized) where
    - steps is list of step_pb2.Step messages
    - finalized is True if the returned steps are finalized, otherwise False.

  Raises:
    errors.MalformedBuild: failed to parse logdog annotation URL.
    errors.StepFetchError: failed to fetch steps.
  """
  try:
    host, project, prefix, stream_name = _parse_logdog_url(annotation_url)
  except ValueError:
    raise errors.MalformedBuild(
        'invalid LogDog URL %r in build %d' % (annotation_url, build_id))

  if host not in allowed_logdog_hosts:
    msg = (
        'build %d references LogDog host %s that is not allowed' %
        (build_id, host))
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
    logging.warning('logdog stream does not exist: %s', annotation_url)
    raise ndb.Return([], False)
  except net.Error as ex:
    # This includes auth errors.
    logging.exception('failed to fetch steps for build %d', build_id)
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


def _get_annotation_url(swarmbucket_build):
  """Returns a LogDog URL of the annotations datagram stream."""

  assert swarmbucket_build.swarming_task_id

  # It is a Swarmbucket build.
  # It MUST have an annotation URL in tags.
  prefix = 'swarming_tag:log_location:'
  for t in swarmbucket_build.tags:
    if t.startswith(prefix):
      return t[len(prefix):]

  raise errors.MalformedBuild(
      'swarmbucket build %d does not have an annotation URL' %
      swarmbucket_build.key.id())


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
