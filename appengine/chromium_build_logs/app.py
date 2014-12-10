# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import HTMLParser
import cgi
import datetime
import json
import logging
import os.path
import pickle
import sys
import time
import urllib

sys.path.append(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), 'third_party'))

from django.utils.html import strip_tags
from google.appengine.api import files
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import deferred
import cloudstorage

import gtest_parser
import suppression_parser


# When processing entities in batches, the size of one batch.
BATCH_SIZE = 100


# Deadline for fetching URLs (in seconds).
URLFETCH_DEADLINE = 30


# Buildbot JSON URLs to use for log scraping.
# TODO(phajdan.jr): Temporarily disabled, resource usage (cost) is too high.
BUILDBOT_ROOTS = [
  'http://build.chromium.org/p/client.dart/json',
  'http://build.chromium.org/p/client.webrtc/json',
  'http://build.chromium.org/p/chromium/json',
  'http://build.chromium.org/p/chromium.win/json',
  'http://build.chromium.org/p/chromium.mac/json',
  'http://build.chromium.org/p/chromium.linux/json',
  'http://build.chromium.org/p/chromium.chromiumos/json',
  #'http://build.chromium.org/p/chromium.fyi/json',
  'http://build.chromium.org/p/chromium.gpu/json',
  #'http://build.chromium.org/p/chromium.flaky/json',
  'http://build.chromium.org/p/chromium.memory/json',
  'http://build.chromium.org/p/chromium.memory.fyi/json',
  'http://build.chromium.org/p/chromium.webkit/json',
  'http://build.chromium.org/p/chromium.webrtc/json',
  'http://build.chromium.org/p/tryserver.chromium/json',
  ]


# Version of the Build entity, to help with database migrations.
BUILD_ENTITY_VERSION = 1


# These values are buildbot constants used for Build and BuildStep.
# This line was copied from master/buildbot/status/builder.py.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY = range(6)

PARSEABLE_STATUSES = (SUCCESS, WARNINGS, FAILURE)


def chunks(iterable, length):
  for i in range(0, len(iterable), length):
    yield iterable[i:i + length]


def for_all_entities(query, callback, param, cursor=None, **kwargs):
  if cursor:
    query.with_cursor(start_cursor=cursor)
  entities = query.fetch(limit=BATCH_SIZE)
  if entities:
    deferred.defer(callback, param, entities, **kwargs)
    deferred.defer(for_all_entities,
                   query,
                   callback,
                   param,
                   query.cursor(),
                   **kwargs)


def buildbot_root_for_log(log_url):
  if not log_url:
    return None
  for buildbot_root in BUILDBOT_ROOTS:
    if log_url.startswith(buildbot_root.replace('/json', '/')):
      return buildbot_root
  return None


def process_status_push(request_body):
  # TODO(phajdan.jr): Temporarily disabled because of performance concerns.
  # urlfetch.fetch('https://chromium-build-health.appspot.com/status_receiver',
  #                request_body,
  #                method=urlfetch.POST,
  #                deadline=URLFETCH_DEADLINE)
  packets = json.loads(cgi.parse_qs(request_body)['packets'][0])
  for packet in packets:
    if packet['event'] == 'buildFinished':
      if 'payload' in packet:
        payload = packet['payload']
      elif 'payload_json' in packet:
        payload = json.loads(packet['payload_json'])
      else:
        payload = {}
      buildbot_root = None
      logging.debug(repr(payload))
      logs = [l[1] for l in payload['build']['logs']]
      for log in logs:
        buildbot_root = buildbot_root_for_log(log)
        if buildbot_root:
          break
      if buildbot_root:
        builder = payload['build']['builderName']
        logging.debug(repr(payload['build']))
        build_number = None
        if 'number' in payload['build']:
          build_number = payload['build']['number']
        elif 'properties' in payload['build']:
          for p in payload['build']['properties']:
            if p[0] == 'buildnumber':
              build_number = p[1]
              break
        if build_number is not None:
          deferred.defer(fetch_build,
                         buildbot_root,
                         builder,
                         build_number,
                         _queue='buildbotfetch')
        else:
          logging.error('cannot figure out build number: %r' % payload)


def iterate_large_result(query):
  tmp = query.fetch(1000)
  for x in tmp:
    yield x
  while tmp:
    tmp = query.with_cursor(query.cursor()).fetch(1000)
    for x in tmp:
      yield x


def html2text(text):
  return HTMLParser.HTMLParser().unescape(strip_tags(text))


class Build(db.Model):
  @classmethod
  def to_key_name(cls, buildbot_root, builder, build_number, times):
    # We use the key to insert the build info atomically, and ensure we only
    # have one entity for each build. The key stores info that should uniquely
    # identify the build.
    return '%d - %s - %s - %d - %d - %d' % (
      1,  # Store a magic number in the key for some flexibility.
      buildbot_root,
      builder,
      build_number,
      long(times[0]),
      long(times[1]))

  # Metadata used for migrations.
  entity_version = db.IntegerProperty(required=True,
                                      default=BUILD_ENTITY_VERSION)

  # Data filled at the time of creation.
  buildbot_root = db.LinkProperty(required=True)
  builder = db.StringProperty(required=True)
  build_number = db.IntegerProperty(required=True)
  time_started = db.DateTimeProperty(required=True)
  time_finished = db.DateTimeProperty(required=True)
  is_fetched = db.BooleanProperty(required=True)

  status = db.IntegerProperty()


class StepName(db.Model):
  name = db.StringProperty(required=True)
  parse_gtest = db.BooleanProperty(required=True)
  parse_suppression = db.BooleanProperty(required=True)


class BuildStep(db.Model):
  # Data filled at the time of creation.
  step_name = db.StringProperty(required=True)
  step_number = db.IntegerProperty(required=True)
  status = db.IntegerProperty(required=True)
  time_started = db.DateTimeProperty(required=True)
  time_finished = db.DateTimeProperty(required=True)
  is_fetched = db.BooleanProperty(required=True)
  is_too_large = db.BooleanProperty(required=True)
  fetch_timestamp = db.DateTimeProperty(required=True)
  stdio_url = db.LinkProperty(required=True)
  gtest_parser_version = db.IntegerProperty(required=True)
  suppression_parser_version = db.IntegerProperty(required=True)

  # Properties below are part of parent entities,
  # but are here to make searches more efficient.
  buildbot_root = db.LinkProperty(required=True)
  builder = db.StringProperty(required=True)
  build_number = db.IntegerProperty(required=True)

  # Data updated separately, after creation.
  log_stdio = blobstore.BlobReferenceProperty()
  log_gs = db.StringProperty()

  def get_build(self):
    return self.parent()


class GTestResult(db.Model):
  build_step = db.ReferenceProperty(BuildStep)

  # Properties below are part of parent entities,
  # but are here to make searches more efficient.
  time_finished = db.DateTimeProperty(required=True)

  # Parser version is updated independently of the parent,
  # i.e. the old results may be in the datastore for a while,
  # they are deleted asynchronously.
  gtest_parser_version = db.IntegerProperty(required=True)

  # Entire entity is filled at the time of creation.
  # Some fields can be empty (i.e. no prefix, no log, etc).
  is_crash_or_hang = db.BooleanProperty(required=True)
  fullname = db.StringProperty(required=True)
  run_time_ms = db.IntegerProperty(required=True, indexed=False)
  log = db.TextProperty()

  def get_build_step(self):
    if self.parent():
      return self.parent()
    return self.build_step

  def get_build(self):
    return self.get_build_step().get_build()

  def get_unix_timestamp(self):
    return int(time.mktime(self.time_finished.timetuple()))


class MemorySuppressionResult(db.Model):
  build_step = db.ReferenceProperty(BuildStep)

  # Properties below are part of parent entities,
  # but are here to make searches more efficient.
  step_name = db.StringProperty(required=True)
  time_finished = db.DateTimeProperty(required=True)

  suppression_parser_version = db.IntegerProperty(required=True)
  name = db.StringProperty(required=True)


class MemorySuppressionSummary(db.Model):
  @classmethod
  def to_key_name(cls, suppression_result):
    # We use the key to update the suppression info atomically, and ensure
    # we only have one entity per suppression-builder combination.
    return '%s - %s - %s - %s - %s' % (
      suppression_result.time_finished.date().replace(day=1).isoformat(),
      suppression_result.build_step.buildbot_root,
      suppression_result.build_step.builder,
      suppression_result.build_step.step_name,
      suppression_result.name)

  monthly_timestamp = db.DateProperty()
  buildbot_root = db.LinkProperty()
  builder = db.StringProperty()
  step_name = db.StringProperty()
  name = db.StringProperty()

  count = db.IntegerProperty(default=0)


def delete_gtest_results(build_step_key):
  """Deletes existing gtest results for given step."""

  build_step = BuildStep.get(build_step_key)
  if not build_step:
    return

  # Record that we've deleted all results.
  build_step.gtest_parser_version = -1
  build_step.put()

  # db.delete(GTestResult.all(keys_only=True).ancestor(build_step))
  db.delete(GTestResult.all(keys_only=True).filter('build_step =', build_step))


def insert_gtest_results(build_step_key):
  """Inserts GTest results into the datastore, replacing any existing ones.
  Also records used parser version."""
  step = BuildStep.get(build_step_key)

  log_contents = ''
  if step.log_gs:
    with cloudstorage.open(step.log_gs) as gs_file:
      log_contents = html2text(gs_file.read().decode('utf-8', 'replace'))
  else:
    try:
      blob_reader = blobstore.BlobReader(step.log_stdio)
      log_contents = html2text(blob_reader.read().decode('utf-8', 'replace'))
    except (ValueError, blobstore.BlobNotFoundError) as e:
      raise deferred.PermanentTaskFailure(e)
  gtest_results = gtest_parser.parse(log_contents)

  to_put = []
  for fullname, result in gtest_results.iteritems():
    # Only store failure results.
    if result['is_successful']:
      continue

    if isinstance(result['log'], unicode):
      log = db.Text(result['log'])
    else:
      log = db.Text(result['log'], encoding='utf-8')
    result_entity = GTestResult(parent=db.Key.from_path(
                                    'GTestResult', str(step.key())),
                                build_step=step,
                                time_finished=step.time_finished,
                                gtest_parser_version=gtest_parser.VERSION,
                                is_crash_or_hang=result['is_crash_or_hang'],
                                fullname=fullname,
                                run_time_ms=result['run_time_ms'],
                                log=log)
    to_put.append(result_entity)
  for chunk in chunks(to_put, BATCH_SIZE):
    db.put(chunk)

  def tx_parser_version():
    step = BuildStep.get(build_step_key)
    orig_parser_version = step.gtest_parser_version
    if step.gtest_parser_version < gtest_parser.VERSION:
      step.gtest_parser_version = gtest_parser.VERSION
      step.put()
    return (orig_parser_version, step.gtest_parser_version)
  _, parser_version = \
      db.run_in_transaction_custom_retries(10, tx_parser_version)

  query = GTestResult.all(keys_only=True)
  query.filter('build_step =', build_step_key)
  query.filter('gtest_parser_version <', parser_version)
  db.delete(query)


def delete_suppression_results(build_step_key):
  """Deletes existing suppression results for given step."""

  build_step = BuildStep.get(build_step_key)
  if not build_step:
    return

  # Record that we've deleted all results.
  build_step.suppression_parser_version = -1
  build_step.put()

  db.delete(MemorySuppressionResult.all(keys_only=True).ancestor(build_step))


def insert_suppression_results(step, suppression_results):
  """Inserts GTest results into the datastore, replacing any existing ones.
  Also records used parser version. Must be used inside a transaction."""
  assert db.is_in_transaction()

  old_parser_version = step.suppression_parser_version

  delete_suppression_results(step.key())

  # Record the parser version used for stored results.
  step.suppression_parser_version = suppression_parser.VERSION
  step.put()

  # Insert new results.
  to_put = []
  for suppression_name in suppression_results:
    to_put.append(MemorySuppressionResult(
        parent=step,
        build_step=step,
        step_name=step.step_name,
        time_finished=step.time_finished,
        suppression_parser_version=step.suppression_parser_version,
        name=suppression_name))
  db.put(to_put)

  # Only update summaries for completely new results.
  if old_parser_version == -1:
    for chunk in chunks(to_put, BATCH_SIZE):
      deferred.defer(update_suppression_summaries,
                     [r.key() for r in chunk],
                     _queue='gtest-summaries')


def update_suppression_summary(suppression_result):
  key_name = MemorySuppressionSummary.to_key_name(suppression_result)

  MemorySuppressionSummary.get_or_insert(
    key_name,
    monthly_timestamp=suppression_result.time_finished.date().replace(day=1),
    buildbot_root=suppression_result.build_step.buildbot_root,
    builder=suppression_result.build_step.builder,
    step_name=suppression_result.build_step.step_name,
    name=suppression_result.name,
    count=0)

  def tx_summary():
    summary = MemorySuppressionSummary.get_by_key_name(key_name)
    summary.count += 1
    summary.put()
  db.run_in_transaction_custom_retries(10, tx_summary)


def update_suppression_summaries(result_keys):
  results = MemorySuppressionResult.get(result_keys)
  for result in results:
    if result:
      update_suppression_summary(result)


def write_blob(data, mime_type):
  """Creates a new blob and writes data to it.
  Returns the key of the created blob."""
  file_name = files.blobstore.create(mime_type=mime_type)
  for chunk in chunks(data, 512*1024):
    with files.open(file_name, 'a') as blob_file:
      blob_file.write(chunk)
  files.finalize(file_name)
  return files.blobstore.get_blob_key(file_name)


def fetch_step(step_key, stdio_url, parse_gtest, parse_suppression):
  """Fetches data about a single build step."""
  step = BuildStep.get(step_key)
  if step.is_fetched:
    return
  step.fetch_timestamp = datetime.datetime.now()
  step.put()

  try:
    stdio_response = urlfetch.fetch(stdio_url, deadline=URLFETCH_DEADLINE)
  except urlfetch.ResponseTooLargeError:
    # Workaround http://code.google.com/p/googleappengine/issues/detail?id=5686
    step.is_fetched = True
    step.is_too_large = True
    step.put()
    return

  if not stdio_response or stdio_response.status_code != 200:
    return

  gs_filename = '/chromium-build-logs/logs/%d/%d/%s' % (
      step.fetch_timestamp.year, step.fetch_timestamp.month, str(step_key))
  with cloudstorage.open(gs_filename, 'w', content_type='text/html') as gs_file:
    gs_file.write(stdio_response.content)

  def tx_step():
    step = BuildStep.get(step_key)
    if step.is_fetched:
      return
    step.log_gs = gs_filename
    step.is_fetched = True
    step.put()
    if parse_gtest and step.status in PARSEABLE_STATUSES:
      deferred.defer(insert_gtest_results,
                     step.key(),
                     _transactional=True,
                     _queue='slow')
    if parse_suppression and step.status in PARSEABLE_STATUSES:
      deferred.defer(reparse_suppression_results,
                     step.key(),
                     step.step_name,
                     _transactional=True,
                     _queue='slow')
  db.run_in_transaction_custom_retries(10, tx_step)


def fetch_steps():
  """Starts a background fetch operation for build steps that need it."""
  parse_gtest = dict((s.name, s.parse_gtest) for s in StepName.all())
  parse_suppression = dict(
      (s.name, s.parse_suppression) for s in StepName.all())

  # Re-try to fetch steps we continuously failed to fetch earlier.
  fetch_timestamp = datetime.datetime.now() - datetime.timedelta(hours=12)

  query = BuildStep.all()
  query.filter('is_fetched =', False)
  query.filter('fetch_timestamp <', fetch_timestamp)
  for step in query:
    deferred.defer(fetch_step,
                   step.key(),
                   step.stdio_url,
                   parse_gtest[step.step_name],
                   parse_suppression[step.step_name],
                   _queue='buildbotfetch')


def fetch_build(buildbot_root, builder, build_number):
  """Fetches data about a single build."""
  build_url = '%s/builders/%s/builds/%d?filter=1' % (buildbot_root,
                                                     urllib.quote(builder),
                                                     build_number)
  build_response = urlfetch.fetch(build_url, deadline=URLFETCH_DEADLINE)
  if not build_response or build_response.status_code != 200:
    return
  build_json = json.loads(build_response.content)

  # Register the step names.
  for step in build_json['steps']:
    StepName.get_or_insert(key_name=step['name'],
                           name=step['name'],
                           parse_gtest=False,
                           parse_suppression=False)

  key_name = Build.to_key_name(buildbot_root,
                               builder,
                               build_number,
                               build_json['times'])
  Build.get_or_insert(
    key_name,
    buildbot_root=buildbot_root,
    builder=builder,
    build_number=build_number,
    time_started=datetime.datetime.fromtimestamp(build_json['times'][0]),
    time_finished=datetime.datetime.fromtimestamp(build_json['times'][1]),
    is_fetched=False,
    status=build_json.get('results', SUCCESS))

  def tx_build():
    build = Build.get_by_key_name(key_name)
    if build.is_fetched:
      return
    to_put = []
    for step in build_json['steps']:
      # Skip steps that didn't run (e.g. when the previous step failed).
      if 'isFinished' not in step:
        continue

      if 'results' in step:
        status = step['results'][0]
      else:
        status = SUCCESS

      if 'logs' not in step:
        # This can happen with steps like 'trigger' that have no logs.
        continue

      logs_dict = dict(step['logs'])
      if 'stdio' in logs_dict:
        stdio_url = logs_dict['stdio']
        log = BuildStep(
          parent=build,
          step_name=step['name'],
          step_number=step.get('step_number', 0),
          status=status,
          time_started=datetime.datetime.fromtimestamp(
            step['times'][0]),
          time_finished=datetime.datetime.fromtimestamp(
            step['times'][1]),
          is_fetched=False,
          is_too_large=False,
          fetch_timestamp=datetime.datetime.now(),
          stdio_url=stdio_url,
          gtest_parser_version=-1,
          suppression_parser_version=-1,
          buildbot_root=build.buildbot_root,
          builder=build.builder,
          build_number=build.build_number)
        to_put.append(log)
    build.is_fetched = True
    db.put(to_put)

  db.run_in_transaction_custom_retries(10, tx_build)

  parse_gtest = dict((s.name, s.parse_gtest) for s in StepName.all())
  parse_suppression = dict(
      (s.name, s.parse_suppression) for s in StepName.all())
  def tx_steps():
    build = Build.get_by_key_name(key_name)
    return BuildStep.all().ancestor(build)
  for build_step in db.run_in_transaction_custom_retries(10, tx_steps):
    fetch_step(build_step.key(),
               build_step.stdio_url,
               parse_gtest[build_step.step_name],
               parse_suppression[build_step.step_name])


def fetch_builder(buildbot_root, builder):
  """Fetches data about builder, if not already fetched."""
  response = urlfetch.fetch('%s/builders/%s/builds/_all' % (
      buildbot_root, urllib.quote(builder)), deadline=URLFETCH_DEADLINE)
  if not response or response.status_code != 200:
    return
  for build in json.loads(response.content).itervalues():
    # Only process complete builds.
    if ('times' not in build or
        len(build['times']) < 2 or
        not build['times'][0] or
        not build['times'][1]):
      continue

    key_name = Build.to_key_name(buildbot_root,
                                 builder,
                                 build['number'],
                                 build['times'])
    def tx_build():
      if not Build.get_by_key_name(key_name):
        deferred.defer(fetch_build,
                       buildbot_root,
                       builder,
                       build['number'],
                       _transactional=True,
                       _queue='buildbotfetch')
    db.run_in_transaction_custom_retries(10, tx_build)


def fetch_builders():
  """Fetches data about builders and build numbers."""
  for buildbot_root in BUILDBOT_ROOTS:
    response = urlfetch.fetch('%s/builders' % buildbot_root,
                              deadline=URLFETCH_DEADLINE)
    if not response or response.status_code != 200:
      continue
    builders = json.loads(response.content)
    for builder in builders:
      deferred.defer(fetch_builder,
                     buildbot_root,
                     builder,
                     _queue='buildbotfetch')


def reparse_suppression_results(build_step_key, _build_step_name):
  step = BuildStep.get(build_step_key)

  log_contents = ''
  if step.log_gs:
    with cloudstorage.open(step.log_gs) as gs_file:
      log_contents = html2text(gs_file.read().decode('utf-8', 'replace'))
  else:
    try:
      blob_reader = blobstore.BlobReader(step.log_stdio)
      log_contents = html2text(blob_reader.read().decode('utf-8', 'replace'))
    except (ValueError, blobstore.BlobNotFoundError), e:
      raise deferred.PermanentTaskFailure(e)
  suppression_results = suppression_parser.parse(log_contents.splitlines(True))
  def tx_reparse():
    step = BuildStep.get(build_step_key)
    insert_suppression_results(step, suppression_results)
    step.put()
  db.run_in_transaction_custom_retries(10, tx_reparse)


def update_parsed_data(_param, chunk):
  """Ensures that all build steps' parsed data is in sync
  with current settings.
  """
  parse_gtest = dict((s.name, s.parse_gtest) for s in StepName.all())
  parse_suppression = dict(
      (s.name, s.parse_suppression) for s in StepName.all())

  for build_step_key in chunk:
    build_step = BuildStep.get(build_step_key)
    if not build_step:
      continue

    try:
      if (parse_gtest[build_step.step_name] and
          build_step.status in PARSEABLE_STATUSES):
        if build_step.gtest_parser_version != gtest_parser.VERSION:
          deferred.defer(insert_gtest_results,
                         build_step.key(),
                         _queue='background',
                         _name='reparse-gtest-%d-%s' % (gtest_parser.VERSION,
                                                        build_step.key()))
      else:
        deferred.defer(delete_gtest_results,
                       build_step.key(),
                       _queue='background',
                       _name='delete-gtest-%s' % build_step.key())
    except (taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
      pass

    try:
      if (parse_suppression[build_step.step_name] and
          build_step.status in PARSEABLE_STATUSES):
        if build_step.suppression_parser_version != suppression_parser.VERSION:
          deferred.defer(
              reparse_suppression_results,
              build_step.key(),
              build_step.step_name,
              _queue='background',
              _name='reparse-suppression-%d-%s' % (suppression_parser.VERSION,
                                                   build_step.key()))
      else:
        deferred.defer(delete_suppression_results,
                       build_step.key(),
                       _queue='background',
                       _name='delete-suppression-%s' % build_step.key())
    except (taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
      pass
