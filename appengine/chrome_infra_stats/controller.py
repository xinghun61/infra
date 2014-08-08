# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
from datetime import datetime
from datetime import timedelta
import json
import logging
import numpy
import pickle
import re
import sys
import time
import traceback
import urllib

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import deferred
from google.appengine.ext import ndb

import cloudstorage as gcs  # pylint: disable=W0403
from pipeline import pipeline  # pylint: disable=W0403
import pipeline.common  # pylint: disable=W0403

import models  # pylint: disable=W0403


masters = [
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
    'chromiumos',
    'client.dart',
    'client.dart.fyi',
    'client.drmemory',
    'client.dynamorio',
    'client.libvpx',
    'client.libyuv',
    'client.nacl',
    'client.nacl.ports',
    'client.nacl.ports.git',
    'client.nacl.sdk',
    'client.nacl.sdk.addin',
    'client.nacl.sdk.mono',
    'client.nacl.toolchain',
    'client.oilpan',
    'client.pagespeed',
    'client.polymer',
    'client.sfntly',
    'client.syzygy',
    'client.v8',
    'client.v8.branches',
    'client.webrtc',
    'client.webrtc.fyi',
    'tryserver.blink',
    'tryserver.chromium',
    'tryserver.chromium.gpu',
    'tryserver.libyuv',
    'tryserver.nacl',
    'tryserver.v8',
    'tryserver.webrtc',
]


def get_builders(master):  # pragma: no cover
  master_key = ndb.Key('Master', master)
  return list(
      models.Builder.query(ancestor=master_key).order(models.Builder.name))


def get_builders_cached(master):  # pragma: no cover
  key = 'builders_for_%s' % master
  cache = memcache.get(key)
  if cache:
    result = pickle.loads(cache)
  else:
    result = get_builders(master)
    memcache.set(key, pickle.dumps(result), time=10*60)
  return result


def get_json(url, follow_redirects=True):  # pragma: no cover
  urlfetch.set_default_fetch_deadline(15)
  max_age = 20
  result = urlfetch.fetch(url, follow_redirects=follow_redirects,
      headers={
        'Cache-Control': 'no-cache,max-age=%d' % max_age,
        'Pragma': 'no-cache'})

  if result.status_code == 200:
    cache_hit = result.headers.get('X-Google-Cache-Control')
    if cache_hit == 'remote-cache-hit':
      cache_age = int(result.headers.get('Age', '-1'))
      if cache_age > max_age:
        raise ValueError(
        'got cached content older than max-age: %d (instead of %d)' % (
          cache_age, max_age))
    return json.loads(result.content)
  else:
    raise ValueError('error fetching %s: %d' % (url, result.status_code))


def get_master_json(master):  # pragma: no cover
  url = ('https://chrome-build-extract.appspot.com/get_master/%s'
      % urllib.quote(master))
  data = get_json(url, follow_redirects=False)
  return data.get('builders', {}).keys()


def get_build_steps(master, builder):  # pragma: no cover
  url = ('https://chrome-build-extract.appspot.com/_ah/api/build_json/v0/json/'
         'recently_finished/%s/%s/120' % (
           urllib.quote(master), urllib.quote(builder)))
  data = get_json(url, follow_redirects=False)
  result = []
  for build_json in data.get('build_jsons', []):
    build = json.loads(build_json)
    assert build.get('times', [None, None])[1] is not None
    properties = {}
    for prop in build.get('properties', []):
      properties[prop[0]] = prop[1]
    revision = properties.get('got_revision',
        properties.get('revision', None))
    starttime = build.get('times', [None, None])[0]
    totaltime = build.get('times', [None, None])[1] - starttime
    buildresult = build.get('results', 0)

    number = build.get('number')

    steps = {}
    build_sigil = 'overall__build__result__'
    steps[build_sigil] = {
      'name': build_sigil,
      'result': buildresult,
      'time': totaltime,
      'starttime': datetime.utcfromtimestamp(starttime),
    }

    for step in build.get('steps', []):
      if not step.get('isStarted') or not step.get('isFinished'):
        continue

      step_name = step.get('name', None)
      step_result = step.get('results', [None, []])[0]
      step_times = step.get('times', [0.0, 0.0])

      steps[step_name] = {
          'name': step_name,
          'result': step_result,
          'time': step_times[1] - step_times[0],
          'starttime': datetime.utcfromtimestamp(step_times[0]),
      }

    result.append({
        'number': number,
        'revision': revision,
        'steps': steps
    })

  return result


@contextlib.contextmanager
def disable_internal_cache():  # pragma: no cover
  context = ndb.get_context()
  policy = context.get_cache_policy()
  context.set_cache_policy(False)
  yield
  context.set_cache_policy(policy)


def get_step_record_iterator(step, hour, end):  # pragma: no cover
  return models.BuildStepRecord().query().filter(
      models.BuildStepRecord.step_start >= hour).filter(
          models.BuildStepRecord.step_start < end).filter(
          models.BuildStepRecord.stepname == step).order(
          models.BuildStepRecord.step_start)


def process_statistical_calculations(record_iterator):  # pragma: no cover
  records = [{'time': r.step_time, 'error': r.result == 2}
      for r in record_iterator]

  times =  list(r['time'] for r in records)

  result = {}
  result['count'] = len(records)
  if result['count'] > 0:
    result['median'] = numpy.percentile(times, 50)
    result['seventyfive'] = numpy.percentile(times, 75)
    result['ninety'] = numpy.percentile(times, 90)
    result['ninetynine'] = numpy.percentile(times, 99)
    result['maximum'] = max(times)
    result['mean'] = numpy.mean(times)
    result['stddev'] = numpy.std(times)

    result['failure_count'] = len(list(e for e in records if e['error']))
    result['failure_rate'] = (float(result['failure_count']) / float(
        result['count'])) * 100.0

  return result


def get_step_records_for_hour(step, hour):  # pragma: no cover
  end = hour + timedelta(hours=1)
  record_iterator = get_step_record_iterator(step, hour, end)
  return get_step_records_internal(step, hour, end, record_iterator)


def get_step_records_for_master_hour(master, step, hour):  # pragma: no cover
  end = hour + timedelta(hours=1)
  record_iterator = get_step_master_iterator(master, step, hour, end)
  return get_step_records_internal('%s-%s' % (master, step),
      hour, end, record_iterator)


def get_step_records_for_master_builder_hour(
    master, builder, step, hour):  # pragma: no cover
  end = hour + timedelta(hours=1)
  record_iterator = get_step_builder_iterator(master, builder, step, hour, end)
  return get_step_records_internal('%s-%s-%s' % (master, builder, step),
      hour, end, record_iterator)


CACHE_THRESH = 10


def get_step_records_internal(record, hour, end, record_iterator,
    finalize=True):  # pragma: no cover
  # Since steps and builds might take up to 24 hours, don't write summaries
  # until we know all the data has trickled in.
  finalize = (finalize and
      hour < (datetime.now() - timedelta(hours=24, minutes=10)))

  record_key = ndb.Key(
      'BuildStatisticRecord', record + '---' + str(hour) +
      '---' + str(end))
  with disable_internal_cache():
    if finalize:
      record_result = record_key.get()
      if record_result:
        logging.info('record found, returning %d %s %s' %(
          record_result.stats.count, record, str(hour)))
        return record_result
    results = process_statistical_calculations(record_iterator)
    logging.info('found %d results %s %s' % (
      results['count'], record, str(hour)))
    record_result = models.BuildStatisticRecord()
    record_result.start_time = hour
    record_result.end_time_exclusive = end
    record_result.record = record
    record_result.stats = models.BuildStepStatistic(**results)
    record_result.key = record_key
    if finalize:
      if results['count'] >= CACHE_THRESH:
        logging.info('finalizing data for %s' % str(record_key))
        record_result.put()
      else:
        logging.info('count less than threshold of %d, not finalizing' % (
          CACHE_THRESH,))
    else:
      logging.info('%s is too early to be finalized, not saving data' %
          str(hour))
    return record_result


def get_step_master_iterator(master, step, hour, end):  # pragma: no cover
  return get_step_record_iterator(step, hour, end).filter(
      models.BuildStepRecord.master == master)


def get_step_builder_iterator(
    master, builder, step, hour, end):  # pragma: no cover
  return get_step_master_iterator(master, step, hour, end).filter(
      models.BuildStepRecord.builder == builder)


def get_step_last_iterator(step, number):  # pragma: no cover
  with disable_internal_cache():
    options = ndb.QueryOptions(limit=number)
    return models.BuildStepRecord().query(default_options=options).filter(
        models.BuildStepRecord.stepname == step).order(
            -models.BuildStepRecord.step_start)


def get_step_master_last_iterator(master, step, number):  # pragma: no cover
  return get_step_last_iterator(step, number).filter(
      models.BuildStepRecord.master == master)


def get_step_builder_last_iterator(
    master, builder, step, number):  # pragma: no cover
  return get_step_master_last_iterator(master, step, number).filter(
            models.BuildStepRecord.builder == builder)


def delete_step_records(step):  # pragma: no cover
  date = datetime.now()
  logging.info('deleting %s summary records before %s' % (
    step, date.isoformat()))
  with disable_internal_cache():
    keys = models.BuildStatisticRecord.query().filter(
      models.BuildStatisticRecord.step == step).filter(
        models.BuildStatisticRecord.generated <= date).fetch(
          1000, keys_only=True)
    while keys:
      logging.info('deleting %d keys of %s summary' % (
        len(keys), step))
      ndb.delete_multi(keys)
      time.sleep(10)
      keys = models.BuildStatisticRecord.query().filter(
        models.BuildStatisticRecord.step == step).filter(
          models.BuildStatisticRecord.generated <= date).fetch(
            1000, keys_only=True)


def delete_all_step_records():  # pragma: no cover
  for step, _ in get_cleaned_steps():
    deferred.defer(delete_step_records, step, _queue='summary-delete',
        _target='stats-backend')


# Python's datetimes aren't JSON-encodable, so we convert them to strings.
class DateEncoder(json.JSONEncoder):  # pragma: no cover
  # pylint: disable=E0202
  def default(self, obj):
    if isinstance(obj, datetime):
      return obj.isoformat()
    return json.JSONEncoder.default(self, obj)


def get_steps_from_builder(master, builder):  # pragma: no cover
  builder_obj = ndb.Key('Master', master, 'Builder', builder).get()
  if builder_obj and builder_obj.steps:
    return builder_obj.steps
  return set()


def get_builders_from_step(step):  # pragma: no cover
  step_obj = ndb.Key('Step', step).get()
  if step_obj and step_obj.builders:
    return step_obj.builders
  return {}


def get_worth_it_steps(disable_cache_lookup=False):  # pragma: no cover
  if not disable_cache_lookup:
    cache = memcache.get('worth_it_steps')
    if cache:
      return cache
  steps = get_cleaned_steps()
  worth_it_steps = [s for s in steps if is_step_worth_it(s[0])]
  memcache.set('worth_it_steps', worth_it_steps)
  return worth_it_steps


def dedup_key(master, builder, buildnumber, stepname):  # pragma: no cover
  return json.dumps((
    master,
    builder,
    buildnumber,
    stepname,
  ), sort_keys=True)


def submit_chunks(steps):  # pragma: no cover
  keys = []
  step_models = []

  with disable_internal_cache():
    for step_dict in steps:
      master = step_dict['master']
      builder = step_dict['builder']
      buildnumber = step_dict['buildnumber']
      stepname = step_dict['stepname']
      key = ndb.Key('BuildStepRecord',
          dedup_key(master, builder, buildnumber, stepname))
      keys.append(key)
      step_models.append(models.BuildStepRecord(key=key, **step_dict))

    in_db = zip(ndb.get_multi(keys), step_models)
    new_builds = filter(lambda x: x[0] is None, in_db)
    ndb.put_multi(x[1] for x in new_builds)


def process_builder(master, builder):  # pragma: no cover
  saw = 0
  wrote = 0
  batch_factor = 1000
  step_chunks = []
  logging.info('checking %s: %s' % (master, builder))
  with disable_internal_cache():
    worth_it = [s[0] for s in get_worth_it_steps()]
    builder_obj = ndb.Key('Master', master, 'Builder', builder).get()
    need_to_update_builder = False
    for build in get_build_steps(master, builder):
      for step_dict in build['steps'].itervalues():
        saw = saw + 1
        if (step_dict['starttime'] + timedelta(seconds=step_dict['time'])) < (
            datetime.now() - timedelta(hours=1, minutes=30)):
          continue

        wrote = wrote + 1
        step_key = ndb.Key('Step', step_dict['name'])
        step_obj = step_key.get()
        if step_obj:
          if step_obj.builders:
            if builder not in step_obj.builders.get(master, []):
              step_obj.builders.setdefault(master, []).append(builder)
              step_obj.put()
          else:
            step_obj.builders = {master: [builder]}
            step_obj.put()
        else:
          models.Step(
              name=step_dict['name'],
              key=step_key,
              builders={master: [builder]}).put()

        if builder_obj:
          step = step_dict['name']
          if step in worth_it:
            if not builder_obj.steps:
              builder_obj.steps = set()
            if step not in builder_obj.steps:
              builder_obj.steps.add(step)
              need_to_update_builder = True
        step_chunks.append({
          'master': master,
          'builder': builder,
          'buildnumber': build['number'],
          'revision': str(build['revision']),
          'stepname': step_dict['name'],
          'step_start': step_dict['starttime'],
          'step_time': step_dict['time'],
          'result': step_dict['result'],
        })
        if len(step_chunks) >= batch_factor:
          logging.info('writing batch of %d' % len(step_chunks))
          deferred.defer(submit_chunks, step_chunks, _queue='step-write', 
              _target='stats-backend')
          step_chunks = []
    if step_chunks:
      logging.info('writing batch of %d' % len(step_chunks))
      deferred.defer(submit_chunks, step_chunks, _queue='step-write',
          _target='stats-backend')
    logging.info('wrote %d out of %d' % (wrote, saw))

    if need_to_update_builder:
      builder_obj.put()


def process_a_master(master):  # pragma: no cover
  logging.info('getting builders for %s' % master)
  builders = get_master_json(master)
  with disable_internal_cache():
    for builder in builders:
      builder_key = ndb.Key('Master', master, 'Builder', builder)
      if not builder_key.get():
        builder_model = models.Builder(
            name=builder,
            key=builder_key,
        )
        builder_model.put()
      logging.info('getting builds for %s/%s' % (master, builder))
      deferred.defer(process_builder, master, builder, _queue='builder-crawl',
          _target='stats-backend')


def process_all_masters():  # pragma: no cover
  for master in masters:
    master_key = ndb.Key('Master', master)
    if not master_key.get():
      master_model = models.Master(
          name=master,
          key=master_key,
      )
      master_model.put()

    deferred.defer(process_a_master, master, _queue='master-crawl',
        _target='stats-backend')


def get_steps(disable_cache_lookup=False):  # pragma: no cover
  if not disable_cache_lookup:
    cache = memcache.get('steps')
    if cache:
      return cache
  with disable_internal_cache():
    steps = [s.name for s in models.Step.query()]
  memcache.set('steps', steps, time=10 * 60)
  return steps


def stash_page(page_name, data):  # pragma: no cover
  bucket = 'chrome-stats-rendered-pages'
  filename = '/%s/page-data/%s' % (bucket, page_name)

  with gcs.open(filename, 'w') as f:
    pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)


def get_page(page_name):  # pragma: no cover
  bucket = 'chrome-stats-rendered-pages'
  filename = '/%s/page-data/%s' % (bucket, page_name)

  try:
    with gcs.open(filename) as f:
      return pickle.load(f)
  except gcs.NotFoundError:
    return None


def get_full_step_count(step):  # pragma: no cover
  data = get_page('step_cache---' + step)
  if not data:
    return -1
  else:
    js = json.loads(data)
    if not js:
      return -1
    return sum(r['stats']['count'] for r in js)


WORTH_IT_HOUR_WINDOW = 40
WORTH_IT_THRESH = 10


def is_step_worth_it(step):  # pragma: no cover
  step_obj = ndb.Key('Step', step).get()
  if not step_obj:
    return False
  with disable_internal_cache():
    query = models.BuildStepRecord.query().filter(
      models.BuildStepRecord.stepname == step).filter(
        models.BuildStepRecord.step_start > (
          datetime.now() - timedelta(hours=WORTH_IT_HOUR_WINDOW))).fetch(
            WORTH_IT_THRESH + 1)
    amount = len(query)
    return amount >= WORTH_IT_THRESH


def is_step_archived(step):  # pragma: no cover
  step_obj = ndb.Key('Step', step).get()
  if not step_obj:
    return False
  if not step_obj.generated:
    return True
  if step_obj.generated > (datetime.now() - timedelta(hours=5)):
    return False
  return not is_step_worth_it(step)


def step_cleanup():  # pragma: no cover
  for step in get_steps():
    if is_step_archived(step):
      logging.info('removing step %s' % step)
      ndb.Key('Step', step).delete()


def get_cleaned_steps(disable_cache_lookup=False):  # pragma: no cover
  if not disable_cache_lookup:
    cache = memcache.get('cleaned_steps')
    if cache:
      return cache
  steps = get_steps()
  ignore_regex = re.compile('Bisection Range')
  ignore_regex2 = re.compile('Working on')
  cleaned_steps = [(s, get_full_step_count(s)) for s in steps
      if not s.endswith('_buildrunner_ignore') and
      not ignore_regex.match(s) and
      not ignore_regex2.match(s)]

  cleaned_steps.sort(key=lambda x: -x[1])

  memcache.set('cleaned_steps', cleaned_steps, time=(30*60))

  return cleaned_steps


@contextlib.contextmanager
def memcache_wrap(key, check_cache=True, expire_time=None):  # pragma: no cover
  result = []
  if check_cache:
    cache = memcache.get(key)
    if cache:
      logging.debug('cache hit: %s' % key)
      result.append(cache)

  yield result

  if result:
    logging.debug('caching result: %s' % key)
    memcache.set(key, result[0], time=expire_time)


class TimeAggregate(pipeline.Pipeline):
  # pylint: disable=W0221,W0223
  def run(self, step=None, end=None, master=None, builder=None, window=None,
      check_cache=True):  # pragma: no cover
    try:
      hybrid_step = step
      if builder:
        hybrid_step = builder + '/' + hybrid_step
      if master:
        hybrid_step = master + '/' + hybrid_step
      memcache_key = 'aggregate_cache-%s-%s-%s-time' % (
          hybrid_step, window, end)
      with memcache_wrap(
          memcache_key, check_cache, expire_time=20*60) as result:
        if result:
          return result.pop()
        start = end - timedelta(seconds=window)
        record_iterator = get_step_record_iterator(step, start, end)
        if builder:
          record_iterator = record_iterator.filter(
              models.BuildStepRecord.builder == builder)
        if master:
          record_iterator = record_iterator.filter(
              models.BuildStepRecord.master == master)
        results = process_statistical_calculations(record_iterator)
        results['step'] = hybrid_step
        results['generated'] = datetime.now()
        results['start'] = str(end - timedelta(seconds=(window)))
        results['center'] = str(end - timedelta(seconds=(window/2.0)))
        results['aggregation_range'] = window
        result.append(results)
        return results
    except Exception:
      exc_type, exc_value, exc_traceback = sys.exc_info()
      for line in traceback.format_exception(
          exc_type, exc_value, exc_traceback):
        logging.error(line)
      raise pipeline.Abort
