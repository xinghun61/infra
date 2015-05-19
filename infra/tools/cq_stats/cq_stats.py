#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
'''Generate stats of CQ usage.'''

import argparse
import calendar
import collections
import datetime
import dateutil.parser
import dateutil.tz
from xml.etree import ElementTree
import infra_libs.logs
import json
import logging
from multiprocessing.pool import ThreadPool
import numbers
import numpy
import re
import subprocess
import sys
import time
import urllib
import urllib2
import urlparse


STATS_URL = 'http://chromium-cq-status.appspot.com'
# Expects % project.
TREE_STATUS_URL = 'http://%s-status.appspot.com'
PROJECTS = {
    'chromium': {
        'tree-status': TREE_STATUS_URL % 'chromium',
        'type': 'git',
        'repo': 'https://chromium.googlesource.com/chromium/src',
    },
    'blink': {
        'tree-status': TREE_STATUS_URL % 'blink',
        'type': 'svn',
        'repo': 'svn://svn.chromium.org/blink/trunk/',
    },
    'skia': {
        'tree-status': TREE_STATUS_URL % 'skia-tree',
        'type': 'git',
        'repo': 'https://skia.googlesource.com/skia',
    },
}
# Map of intervals to minutes.
INTERVALS = {
    'week': 60 * 24 * 7,
    'day': 60 * 24,
    'hour': 60,
    '15min': 15,
}
VALID_REASONS = collections.OrderedDict([
    ('manual-cancel', {
        'item': 'stopped manually',
        'message': 'stopped manually (CQ box was unchecked)',
    }),
    ('missing-lgtm',  {
        'item': 'missed LGTM',
        'message': 'are missing LGTM',
    }),
    ('not-lgtm',  {
        'item': 'NOT LGTMs',
        'message': 'have been disapproved (NOT LGTM)',
    }),
    ('failed-patch', {
        'item': 'failures',
        'message': 'failed to apply patch',
    }),
    ('invalid-delimiter', {
        'item': 'errors',
        'message': 'have incorrect CQ_EXTRA_TRYBOTS flag',
    }),
    ('failed-presubmit-bot', {
        'item': 'failures',
        'message': 'failed presubmit bot (often due to missing OWNERS LGTM)',
    }),
    ('failed-remote-ref-presubmit', {
        'item': 'failures',
        'message': 'did not contain NOTRY & NOPRESUBMIT for non master remote '
                   'ref',
    }),
])
FLAKY_REASONS = collections.OrderedDict([
    ('failed-commit', {
        'item': 'failures',
        'message': 'failed to commit',
    }),
    ('failed-jobs', {
        'item': 'failures',
        'message': 'failed jobs (excluding presubmit)',
    }),
    ('failed-to-trigger', {
        'item': 'failures',
        'message': 'failed to trigger jobs',
    }),
    ('failed-presubmit-check', {
        'item': 'failures',
        'message': 'failed presubmit check',
    }),
])
KNOWN_REASONS = collections.OrderedDict()
KNOWN_REASONS.update(VALID_REASONS)
KNOWN_REASONS.update(FLAKY_REASONS)

REASONS = collections.OrderedDict()
REASONS.update(KNOWN_REASONS)
REASONS['failed-unknown'] = {
    'item': 'failures',
    'message': 'failed for any other reason',
}


def parse_args():
  parser = argparse.ArgumentParser(description=sys.modules['__main__'].__doc__)
  parser.add_argument(
      '--project',
      required=True,
      choices=PROJECTS.keys(),
      help='Collect stats about this project.')
  parser.add_argument(
      '--bot', type=str, dest='bots',
      action='append',
      default=['blink-deps-roller@chromium.org',
               'chrome-admin@google.com',
               'chrome-release@google.com',
               'chromeos-commit-bot@chromium.org',
               'skia-deps-roller@chromium.org',
              ],
      help=('Add an author to be treated as a bot. '
            'Repeat to add several bots. Default: %(default)s.'))
  parser.add_argument(
      '--seq', action='store_true',
      help='Run everything sequentially for debugging.')
  parser.add_argument(
      '--thread-pool', type=int, default=200,
      help='Fetch data using this many parallel threads. Default=%(default)s.')
  parser.add_argument(
      '--list-rejections', action='store_true',
      help='List rejected CLs and reasons for rejection.')
  parser.add_argument(
      '--list-false-rejections', action='store_true',
      help='List CLs that were committed in more than one attempt.')
  parser.add_argument(
      '--use-logs', action='store_true',
      default=True,
      help=('On by default. '
            'Fetch the detailed logs and recompute the stats in this script, '
            'instead of fetching precomputed stats. '
            'Slower, but more accurate, and helps validate the cached stats.'))
  parser.add_argument(
      '--use-cache',
      dest='use_logs',
      action='store_false',
      help=('Fetch the cached stats from the app. Opposite to --use-logs.'))
  parser.add_argument(
      '--date',
      help='Start date of stats YYYY-MM-DD[ HH[:MM]]. Default: --range ago.')
  parser.add_argument('--range',
                      choices=INTERVALS.keys(),
                      default='week',
                      help='Time range to print stats for.')
  infra_libs.logs.add_argparse_options(parser, default_level=logging.ERROR)

  args = parser.parse_args()

  if args.date:
    args.date = date_from_string(args.date)
  else:
    args.date = (datetime.datetime.now() -
                 datetime.timedelta(minutes=INTERVALS[args.range]))

  return args


def date_from_string(iso_str):
  try:
    return dateutil.parser.parse(iso_str)
  except ValueError:
    pass
  raise ValueError('Unrecognized date/time format: %s' % iso_str)


def date_from_timestamp(timestamp):
  return datetime.datetime.utcfromtimestamp(float(timestamp))


def date_from_git(date_str):
  """If date_str is not valid or None, return None."""
  if not date_str:
    return None
  date = None
  try:
    date = dateutil.parser.parse(date_str)
    if date.tzinfo:
      # Convert date to UTC timezone.
      date = date.astimezone(dateutil.tz.tzutc())
      # Make date offset-naive like the other date objects in this module.
      date = date.replace(tzinfo=None)
  except ValueError:
    pass
  return date


def local_date_to_timestamp(date):
  return time.mktime(date.timetuple())


def local_to_utc(local_time):
  timestamp = local_date_to_timestamp(local_time)
  utcTime = datetime.datetime.utcfromtimestamp(timestamp)
  return utcTime


def fetch_json(url):
  result = {'error': '404'}
  delays = [0.0, 0.5, 1.0, 2.0]
  for retry in range(len(delays)):
    if retry:
      time.sleep(delays[retry])
    try:
      result = json.loads(urllib2.urlopen(url).read())
      return result
    except (IOError, ValueError) as e:
      logging.warning('Failed to fetch (attempt %d) %s: %s', retry + 1, url, e)
  logging.error('Permanently failed to fetch %s: %s', url, e)
  return result


def fetch_tree_status(project, end_date, start_date=None, limit=1000):
  """Fetch all tree events in the given interval.

  Args:
    project (str): e.g. 'chromium' or 'blink'.
    end_date (datetime):
    start_date (datetime): define the time interval in local timezone.
    limit (int): max. number of events.

  Returns:
    List of events {'open': bool, 'date': datetime} sorted by date.
  """
  end_timestamp = int(time.mktime(end_date.timetuple()))
  params = {
      'format': 'json',
      'limit': limit,
      # Confusingly, chromium-status app defines the range as
      # endTime <= t < startTime.
      'startTime': end_timestamp,
  }
  if start_date:
    params['endTime'] = int(time.mktime(start_date.timetuple()))
  query = 'allstatus?' + urllib.urlencode(params)
  url = urlparse.urljoin(PROJECTS[project]['tree-status'], query)
  logging.debug('Fetching %s', url)
  status = fetch_json(url)
  # Bug in AE app: it may return events outside of time range.
  def entry(event):
    date_utc = date_from_string(event['date'])
    date_local = date_from_timestamp(calendar.timegm(date_utc.utctimetuple()))
    return {'date': date_local,
            'open': event['general_state'] == 'open'}
  def in_range(entry):
    logging.debug('in_range(%r)', entry)
    if entry['date'] >= end_date:
      return False
    if not start_date:
      return True
    return start_date <= entry['date']

  if not status or type(status) is not list:
    status = []
  status = [entry(event) for event in status]
  status = sorted([e for e in status if in_range(e)], key=lambda e: e['date'])
  return status


def fetch_git_page(repo_url, cursor=None, page_size=2000):
  """Fetch one page worth of logs from gitiles."""
  params = {
      'pretty': 'full',
      'format': 'JSON',
      'n': page_size,
  }
  if cursor:
    params.update({'s': cursor})
  url = '%s/%s?%s' % (repo_url, '/+log/master', urllib.urlencode(params))
  logging.debug('fetch_git_page: url = %s', url)
  try:
    # Strip off the anti-XSS string from the response.
    response = urllib2.urlopen(url)
    lines = [l.rstrip() for l in response if l.rstrip() != ")]}'"]
    raw_data = ''.join(lines)
    page = json.loads(raw_data)
  except (IOError, ValueError) as e:
    page = {}
    logging.error('Failed to fetch a page: %s', e)
  return page


def fetch_git_logs(repo, from_date, to_date):
  """Fetch all logs from Gitiles for the given date range.

  Gitiles does not natively support time ranges, so we just fetch
  everything until the range is covered. Assume that logs are ordered
  in reverse chronological order.
  """
  cursor = ''
  commit_date = to_date
  data = []
  while cursor is not None:
    page = fetch_git_page(repo, cursor)
    logs = page.get('log', [])
    cursor = page.get('next')
    for log in logs:
      committer = log.get('committer', {})
      commit_date = date_from_git(committer.get('time'))
      if not commit_date:
        continue
      if commit_date > to_date:
        continue
      if commit_date < from_date:
        break
      data.append({
          'author': log.get('author', {}).get('email'),
          'date': commit_date,
          'commit-bot': bool('commit-bot' in committer.get('email', '')),
          'revision': log.get('commit'),
      })

    if commit_date < from_date:
      break
  return data


def fetch_svn_logs(repo, from_date, to_date):
  from_date = local_to_utc(from_date)
  to_date = local_to_utc(to_date)
  range_str = (
      '{%s +0000}:{%s +0000}' % (from_date, to_date))
  out = subprocess.check_output(
      ['svn', 'log', '--with-all-revprops', '--xml', repo, '-r', range_str])
  data = []
  for logentry in ElementTree.XML(out).findall('logentry'):
    date_str = logentry.find('date').text
    date = date_from_string(date_str)
    entry = {
        'author': logentry.find('author').text,
        'date': date,
        'revprops': {},
        'commit-bot': False,
    }
    revprops = logentry.find('revprops')
    if revprops is not None:
      for revprop in revprops.findall('property'):
        entry['revprops'][revprop.attrib['name']] = revprop.text
        if revprop.attrib['name'] == 'commit-bot':
          entry['commit-bot'] = True
    data.append(entry)
  return data


def fetch_stats(args, begin_date=None, stats_range=None):
  if not begin_date:
    begin_date = args.date
  if not stats_range:
    stats_range = args.range
  if begin_date:
    timestamp = (int(local_date_to_timestamp(begin_date)) +
                 INTERVALS[stats_range] * 60)
  else:
    timestamp = int(time.time())

  params = {
      'project': args.project,
      'interval_minutes': INTERVALS[stats_range],
      'end': timestamp,
      'count': 2, # Fetch requested and previous set, for comparison.
  }

  query = 'stats/query?' + urllib.urlencode(params)
  url = urlparse.urljoin(STATS_URL, query)
  logging.debug('Fetching %s', url)
  return fetch_json(url)


# "Dangerous default value []": pylint: disable=W0102
def fetch_cq_logs(start_date=None, end_date=None, filters=[]):
  begin_time = None
  end_time = None
  if start_date:
    begin_time = int(time.mktime(start_date.timetuple()))
  if end_date:
    end_time = int(time.mktime(end_date.timetuple()))
  results = []
  cursor = None
  while True:
    params = {}
    if begin_time:
      params['begin'] = begin_time
    if end_time:
      params['end'] = end_time
    if cursor:
      params['cursor'] = cursor
    query = 'query/%s?%s' % ('/'.join(filters), urllib.urlencode(params))
    url = urlparse.urljoin(STATS_URL, query)
    logging.debug('Fetching %s', url)
    data = fetch_json(url)
    results.extend(data.get('results', []))
    logging.info('fetch_cq_logs: Got %d results', len(results))
    logging.debug('  %s', '\n  '.join(['%s %s' % (
        patch_url((r.get('fields', {}).get('issue', 0),
                   r.get('fields', {}).get('patchset', 0))),
        r.get('fields', {}).get('action', '')) for r in results]))
    cursor = data.get('cursor', None)
    if not data.get('more', False) or not cursor:
      break

  return results


def default_stats():
  """Generate all the required stats fields with default values."""
  stats = {
      'begin': datetime.datetime.now(),
      'end': datetime.datetime(1, 1, 1),
      'issue-count': 0,
      'patchset-count': 0,
      'attempt-count': 0,
      'patch_stats': {},
      'patchset-false-reject-count': 0,  # Deprecated stats?
      'attempt-reject-count': 0,  # Num. of rejected attempts
      'attempt-false-reject-count': 0,  # Num. of falsely rejected attempts
      'false-rejections': [],  # patches with falsely rejected attempts
      'rejections': [],        # patches with rejected attempts
      'rejected-patches': set(),  # Patches that never committed
      'patchset-commit-count': 0,
      'patchset-total-commit-queue-durations': derive_list_stats([0]),
      'patchset-durations': derive_list_stats([0]),
      'patchset-committed-durations': derive_list_stats([0]),
      'patchset-attempts': derive_list_stats([0]),
      'patchset-committed-attempts': derive_list_stats([0]),
      'jobs': {},
      'tree': {'open': 0.0, 'total': 0.0},
      'usage': {},
  }
  for reason in REASONS:
    stats[reason] = []
  return stats


def organize_stats(stats, init=None):
  """Changes cached lists of stats into dictionaries.

  Args:
    stats (dict): set of stats as returned by chromium-cq-status.

  Returns:
    result (dict): mapping stat.name -> <stats json>.  If init is given,
    add to those stats rather than compute them from scratch.
  """
  if 'results' not in stats:
    return None
  result = init if init else default_stats()
  for dataset in stats['results']:
    result['begin'] = min(
        date_from_timestamp(dataset['begin']),
        result.get('begin', datetime.datetime.now()))
    result['end'] = max(date_from_timestamp(dataset['end']), result['end'])
    re_trybot_pass_count = re.compile('^trybot-(.+)-pass-count$')
    re_trybot_false_reject_count = re.compile(
        '^trybot-(.+)-false-reject-count$')
    assert 'jobs' in result and isinstance(result['jobs'], dict)
    for data in dataset['stats']:
      if data['type'] == 'count':
        result[data['name']] = data['count']
        match_pass = re_trybot_pass_count.match(data['name'])
        match_false_reject = re_trybot_false_reject_count.match(data['name'])
        if match_pass:
          job_name = match_pass.group(1)
          result['jobs'].setdefault(job_name, {
              'pass-count': 0,
              'false-reject-count': 0,
          })
          result['jobs'][job_name]['pass-count'] += data['count']
          logging.debug('Job %s passed %d times. Jobs: %r',
                        job_name, data['count'], result['jobs'])
        if match_false_reject:
          job_name = match_false_reject.group(1)
          result['jobs'].setdefault(job_name, {
              'pass-count': 0,
              'false-reject-count': 0,
          })
          result['jobs'][job_name]['false-reject-count'] += data['count']
          logging.debug('Job %s flakily failed %d times',
                        job_name, data['count'])
      else:
        assert data['type'] == 'list'
        result[data['name']] = {
            '10': data['percentile_10'],
            '25': data['percentile_25'],
            '50': data['percentile_50'],
            '75': data['percentile_75'],
            '90': data['percentile_90'],
            '95': data['percentile_95'],
            '99': data['percentile_99'],
            'min': data['min'],
            'max': data['max'],
            'mean': data['mean'],
            'size': data['sample_size'],
        }
  return result


def derive_list_stats(series):
  if not series:
    series = [0]
  return {
      '10': numpy.percentile(series, 10),
      '25': numpy.percentile(series, 25),
      '50': numpy.percentile(series, 50),
      '75': numpy.percentile(series, 75),
      '90': numpy.percentile(series, 90),
      '95': numpy.percentile(series, 95),
      '99': numpy.percentile(series, 99),
      'min': min(series),
      'max': max(series),
      'mean': numpy.mean(series),
      'size': len(series),
  }


def sort_by_count(elements):
  return sorted(elements, key=lambda p: p['count'], reverse=True)


def stats_by_count_entry(patch_stats, name, patch, reasons):
  entry = {
      'count': patch_stats[name],
      'patch_id': patch,
      'failed-jobs-details': patch_stats['failed-jobs-details']
  }
  for n in reasons:
    if n in patch_stats:
      entry[n] = patch_stats[n]
      assert type(entry[n]) is int, 'Bad type in %s[%s]: %r\nEntry=%r' % (
        patch, n, entry[n], entry)
  return entry


# "Dangerous default value []": pylint: disable=W0102
def stats_by_count(patch_stats, name, reasons=[]):
  return sort_by_count([
      stats_by_count_entry(patch_stats[p], name, p, reasons)
      for p in patch_stats if patch_stats[p].get(name)])


def _derive_stats_from_patch_stats(stats):
  patch_stats = stats['patch_stats']
  stats['attempt-count'] = sum(
      patch_stats[p]['attempts'] for p in patch_stats)
  stats['patchset-false-reject-count'] = sum(
      patch_stats[p]['false-rejections'] for p in patch_stats)
  stats['attempt-reject-count'] = sum(
      patch_stats[p]['rejections'] for p in patch_stats)
  stats['rejected-patches'] = set(
      p for p in patch_stats if not patch_stats[p]['committed'])
  stats['false-rejections'] = stats_by_count(
      patch_stats, 'false-rejections', REASONS)
  stats['rejections'] = stats_by_count(patch_stats, 'rejections', REASONS)
  for r in REASONS:
    stats[r] = stats_by_count(patch_stats, r, set(REASONS) - set([r]))

  stats['patchset-commit-count'] = len([
      p for p in patch_stats if patch_stats[p]['committed']])
  stats['patchset-total-commit-queue-durations'] = derive_list_stats([
      patch_stats[p]['patchset-duration-wallclock'] for p in patch_stats])
  stats['patchset-durations'] = derive_list_stats([
      patch_stats[p]['patchset-duration'] for p in patch_stats])
  stats['patchset-committed-durations'] = derive_list_stats([
      patch_stats[p]['patchset-duration'] for p in patch_stats
      if patch_stats[p]['committed']])
  stats['patchset-attempts'] = derive_list_stats([
      patch_stats[p]['attempts'] for p in patch_stats])
  stats['patchset-committed-attempts'] = derive_list_stats([
      patch_stats[p]['attempts'] for p in patch_stats
      if patch_stats[p]['committed']])


def derive_stats(args, begin_date, init_stats=None):
  """Process raw CQ updates log and derive stats.

  Fetches raw CQ events and returns the same format as organize_stats().
  If ``init_stats`` are given, preserve the jobs stats and replace the
  other stats.
  """
  stats = init_stats or default_stats()
  filters = ['project=%s' % args.project, 'action=patch_stop']
  end_date = begin_date + datetime.timedelta(minutes=INTERVALS[args.range])
  results = fetch_cq_logs(begin_date, end_date, filters=filters)
  if not results:
    return stats

  stats['begin'] = date_from_timestamp(results[-1]['timestamp'])
  stats['end'] = date_from_timestamp(results[0]['timestamp'])
  # Create map issue:patchset -> #attempts
  patches, issues = set(), set()
  for reason in results:
    issues.add(reason['fields']['issue'])
    patches.add((reason['fields']['issue'], reason['fields']['patchset']))
  stats['issue-count'] = len(issues)
  stats['patchset-count'] = len(patches)
  patch_stats = {}
  # Fetch and process each patchset log
  def get_patch_stats(patch_id):
    return derive_patch_stats(end_date, patch_id)

  if args.seq or not args.thread_pool:
    iterable = map(get_patch_stats, patches)
  else:
    pool = ThreadPool(min(args.thread_pool, len(patches)))
    iterable = pool.imap_unordered(get_patch_stats, patches)
  for patch_id, pstats in iterable:
    if not pstats['supported']:
      continue
    patch_stats[patch_id] = pstats

  stats['patch_stats'] = patch_stats
  _derive_stats_from_patch_stats(stats)
  return stats


def patch_url(patch_id):
  return '%s/patch-status/%s/%s' % ((STATS_URL,) + patch_id)


def parse_json(obj, return_type=None):
  """Attempt to interpret a string as JSON.

  Guarantee the return type if given, pass through otherwise.
  """
  result = obj
  if type(obj) in [str, unicode]:
    try:
      result = json.loads(obj)
    except ValueError as e:
      logging.error('Could not decode json in "%s": %s', obj, e)
  # If the type is wrong, return an empty object of the correct type.
  # In most cases, casting to the required type will not work anyway
  # (e.g. list to dict).
  if return_type and type(result) is not return_type:
    result = return_type()
  return result


def parse_failing_tryjobs(message):
  """Parse the message to extract failing try jobs."""
  builders = []
  msg_lines = message.splitlines()
  for line in msg_lines[1:]:
    words = line.split(None, 1)
    if not words:
      continue
    builder = words[0]
    builders.append(builder)
  return builders


def derive_patch_stats(end_date, patch_id):
  """``patch_id`` is a tuple (issue, patchset)."""
  results = fetch_cq_logs(end_date=end_date, filters=[
      'issue=%s' % patch_id[0], 'patchset=%s' % patch_id[1]])
  # The results should already ordered, but sort it again just to be sure.
  results = sorted(results, key=lambda r: r['timestamp'], reverse=True)
  logging.debug('derive_patch_stats(%r): fetched %d entries.',
                patch_id, len(results))
  # Group by attempts
  attempts = []

  def new_attempt():
    attempt_empty = {
        'id': 0,
        'begin': 0.0,
        'end': 0.0,
        'duration': 0.0,
        'actions': [],
        'committed': False,
        'reason': {},
        'supported': True,
    }
    for reason in REASONS:
      attempt_empty[reason] = False
    return attempt_empty

  def add_attempt(attempt, counter):
    """Create a new attempt from accumulated actions."""
    assert attempt['actions']
    attempt['id'] = counter
    attempt['duration'] = attempt['end'] - attempt['begin']
    known_reasons = [r for r in KNOWN_REASONS if attempt[r]]
    if not attempt['committed'] and not known_reasons:
      attempt['failed-unknown'] = True
    logging.debug(
        'add_attempt: #%d (%s)',
        attempt['id'],
        ', '.join([r for r in REASONS if attempt[r]]))
    attempts.append(attempt)

  # An attempt is a set of actions between patch_start and patch_stop
  # actions. Repeated patch_start / patch_stop actions are ignored.
  attempt = new_attempt()
  failing_builders = {}
  state = 'stop'
  attempt_counter = 0
  for result in reversed(results):
    action = result['fields'].get('action')
    if state == 'stop':
      if action == 'patch_start':
        state = 'start'
        attempt['begin'] = result['timestamp']
    if state != 'start':
      continue
    attempt['actions'].append(result)
    if action == 'patch_stop':
      attempt['end'] = result['timestamp']
      message = result['fields'].get('message', '')
      if 'CQ bit was unchecked on CL' in message:
        attempt['manual-cancel'] = True
      if 'No LGTM' in message:
        attempt['missing-lgtm'] = True
      if 'A disapproval has been posted' in message:
        attempt['not-lgtm'] = True
      if 'Transient error: Invalid delimiter' in message:
        attempt['invalid-delimiter'] = True
      if 'Failed to commit' in message:
        attempt['failed-commit'] = True
      if('Failed to apply patch' in message or
         'Failed to apply the patch' in message):
        attempt['failed-patch'] = True
      if 'Presubmit check' in message:
        attempt['failed-presubmit-check'] = True
      if 'CLs for remote refs other than refs/heads/master' in message:
        attempt['failed-remote-ref-presubmit'] = True
      if 'Try jobs failed' in message:
        if 'presubmit' in message:
          attempt['failed-presubmit-bot'] = True
        else:
          attempt['failed-jobs'] = message
          builders = parse_failing_tryjobs(message)
          for b in builders:
            failing_builders.setdefault(b, 0)
            failing_builders[b] += 1
      if 'Exceeded time limit waiting for builds to trigger' in message:
        attempt['failed-to-trigger'] = True
      attempt_counter += 1
      add_attempt(attempt, attempt_counter)
      attempt = new_attempt()
      state = 'stop'
      continue
    if action == 'patch_committed':
      attempt['committed'] = True
    # TODO(sergeyberezin): enable this after this action is stable in CQ.
    if action == 'patch_failed':
      attempt['reason'] = parse_json(
          result['fields'].get('reason', {}), return_type=dict)
      logging.info('Attempt reason: %r', attempt['reason'])
      if attempt['reason'].get('fail_type') == 'reviewer_lgtm':
        attempt['missing-lgtm'] = True
      if attempt['reason'].get('fail_type') == 'commit':
        attempt['failed-commit'] = True
      if attempt['reason'].get('fail_type') == 'simple try job':
        failed_jobs = parse_json(attempt['reason'].get(
            'fail_details', [('unknown_master', 'unknown_bot')]))
        # Remove presubmit bot - it's accounted separately.
        failed_jobs = [j for j in failed_jobs if 'presubmit' in j[1]]
        attempt['failed-jobs'] = failed_jobs
    if action == 'verifier_custom_trybots':
      attempt['supported'] = False

  stats = {}
  committed_set = set(a['id'] for a in attempts if a['committed'])
  stats['committed'] = len(committed_set)
  stats['attempts'] = len(attempts)
  stats['rejections'] = stats['attempts'] - stats['committed']
  stats['supported'] = all(a['supported'] for a in attempts)

  logging.info('derive_patch_stats: %s has %d attempts, committed=%d',
               patch_url(patch_id), len(attempts), stats['committed'])

  valid_reasons_set = set()
  for reason in VALID_REASONS:
    s = set(a['id'] for a in attempts if a[reason])
    stats[reason] = len(s)
    valid_reasons_set.update(s)
  for reason in set(REASONS) - set(VALID_REASONS):
    stats[reason] = len(set(a['id'] for a in attempts if a[reason]))

  # Populate failed builders.
  stats['failed-jobs-details'] = failing_builders

  stats['false-rejections'] = 0
  if stats['committed']:
    stats['false-rejections'] = len(
        set(a['id'] for a in attempts) - committed_set - valid_reasons_set)
  # Sum of attempt duration.
  stats['patchset-duration'] = sum(a['duration'] for a in attempts)
  if attempts:
    stats['patchset-duration-wallclock'] = (
        attempts[-1]['end'] - attempts[0]['begin'])
  else:
    stats['patchset-duration-wallclock'] = 0.0
  return patch_id, stats


def derive_tree_stats(project, start_date, end_date):
  """Given a list of tree status events, derive tree closure stats."""
  # Fetch one more event right before the range, so we know the
  # initial tree status.
  status = (fetch_tree_status(project, end_date=start_date, limit=1) +
            fetch_tree_status(project, end_date, start_date))
  stats = {'open': 0.0, 'total': (end_date - start_date).total_seconds()}
  if not status:
    return stats

  logging.debug('Tree status:\n%s', '\n'.join(['  %r' % e for e in status]))

  is_open = status[0]['open']
  curr_date = start_date
  for event in status[1:]:
    delta = event['date'] - curr_date
    if is_open and not event['open']:
      stats['open'] += delta.total_seconds()
      logging.debug('Tree was open from %s to %s for %s (total of %s)',
                    curr_date, event['date'],
                    delta, datetime.timedelta(seconds=stats['open']))
    if not is_open:
      curr_date = event['date']
    is_open = event['open']

  # Account for the remaining time after the last event.
  if is_open:
    delta = end_date - curr_date
    stats['open'] += delta.total_seconds()
    logging.debug('Tree was open from %s to %s for %s (total of %s)',
                  curr_date, end_date,
                  delta, datetime.timedelta(seconds=stats['open']))
  return stats


def derive_log_stats(log_data, bots):
  # Calculate stats.
  cq_commits = [v for v in log_data if v['commit-bot']]
  users = {}
  for commit in cq_commits:
    users[commit['author']] = users.get(commit['author'], 0) + 1
  committers = {}
  manual_committers = {}
  bot_committers = {}
  bot_manual_committers = {}
  for commit in log_data:
    committers[commit['author']] = committers.get(commit['author'], 0) + 1
    if not commit['commit-bot']:
      manual_committers[commit['author']] = manual_committers.get(
          commit['author'], 0) + 1
    if commit['author'] in bots:
      bot_committers[commit['author']] = bot_committers.get(
          commit['author'], 0) + 1
      if not commit['commit-bot']:
        bot_manual_committers[commit['author']] = bot_manual_committers.get(
            commit['author'], 0) + 1

  stats = {}
  stats['cq_commits'] = len(cq_commits)
  stats['total_commits'] = len(log_data)
  stats['users'] = len(users)
  stats['committers'] = len(committers)
  stats['manual_committers'] = len(manual_committers)
  stats['manual_commits'] = sum(x for x in manual_committers.itervalues())
  stats['bot_committers'] = len(bot_committers)
  stats['bot_commits'] = sum(x for x in bot_committers.itervalues())
  stats['bot_manual_commits'] = sum(
      x for x in bot_manual_committers.itervalues())
  stats['manual_only_committers'] = {
      a: c for a, c in committers.iteritems()
      if c == manual_committers.get(a, 0)}
  return stats

def derive_git_stats(project, start_date, end_date, bots):
  log_data = fetch_git_logs(PROJECTS[project]['repo'], start_date, end_date)
  return derive_log_stats(log_data, bots)


def derive_svn_stats(project, start_date, end_date, bots):
  log_data = fetch_svn_logs(PROJECTS[project]['repo'], start_date, end_date)
  return derive_log_stats(log_data, bots)


def percentage_tuple(data, total):
  num_data = data if isinstance(data, numbers.Number) else len(data)
  num_total = total if isinstance(total, numbers.Number) else len(total)
  percent = 100. * num_data / num_total if num_total else 0.
  return num_data, num_total, percent


def percentage(data, total):
  return percentage_tuple(data, total)[2]


def round_timedelta(seconds):
  # We never care about the milliseconds when printing timedeltas:
  return datetime.timedelta(seconds=round(seconds))


def output(fmt='', *args):
  """An equivalent of print to mock out in testing."""
  print fmt % args


def print_attempt_counts(stats, name, message, item_name='',
                         details=False, committed=None, indent=0,
                         print_zero=False):
  """Print a summary of a ``name`` slice of attempts.

  |committed|: None=print all, True=only committed patches, False=only
   rejected patches.

  |print_zero|: print stats even if no attempts match."""
  if not item_name:
    item_name = message
  patches = [
      p for p in stats[name]
      if committed is None or
      bool(stats['patch_stats'][p['patch_id']]['committed']) is committed]
  count = sum(p['count'] for p in patches)
  if not print_zero and not count:
    return

  failing_builders = {}
  for p in patches:
    for b, cnt in p['failed-jobs-details'].iteritems():
      failing_builders.setdefault(b, {})
      failing_builders[b][p['patch_id']] = cnt

  indent_str = ''.join(' ' for _ in range(indent))
  if message.startswith('failed jobs'):
    output(
        '%s%4d attempt%s (%.1f%% of %d attempts) %s: %d in %d%s patches',
        indent_str, count, ' ' if count == 1 else 's',
        percentage(count, stats['attempt-count']),
        stats['attempt-count'],
        message,
        sum(sum(d.values()) for d in failing_builders.values()),
        len(patches),
        {True: ' committed', False: ' uncommitted'}.get(committed, ''))
  else:
    output(
        '%s%4d attempt%s (%.1f%% of %d attempts) %s in %d%s patches',
        indent_str, count, ' ' if count == 1 else 's',
        percentage(count, stats['attempt-count']),
        stats['attempt-count'],
        message,
        len(patches),
        {True: ' committed', False: ' uncommitted'}.get(committed, ''))
  if details:
    lines = []
    for p in patches:
      line = '      %d %s %s'  % (
          p['count'], item_name, patch_url(p['patch_id']))
      causes = ['%d %s' % (p['failed-jobs-details'][k], k)
                for k in p['failed-jobs-details']]
      line += ' (%s)' % ', '.join(causes)
      lines.append(line)
    output('\n'.join(lines))
    output()


def print_duration(name, stats, print_name=None):
  if not print_name:
    print_name = name.capitalize()
  cq_only = round_timedelta(stats['patchset-durations'][name])
  wallclock = round_timedelta(
      stats['patchset-total-commit-queue-durations'][name])
  output('\n%s duration in CQ trying a patch:', print_name)
  output(
      '  wallclock:       %8s (%3d min).',
      wallclock, round(wallclock.total_seconds() / 60.0))
  output(
      '  sum of attempts: %8s (%3d min).',
      cq_only, round(cq_only.total_seconds() / 60.0))


def print_usage(stats):
  if not stats['usage']:
    return
  output()
  output(
      'CQ users:      %6d out of %6d total committers %6.2f%%',
      stats['usage']['users'], stats['usage']['committers'],
      percentage(stats['usage']['users'], stats['usage']['committers']))
  fmt_str = (
      '  Committed    %6d out of %6d commits          %6.2f%%. ')
  data = percentage_tuple(stats['usage']['cq_commits'],
                          stats['usage']['total_commits'])
  if stats['usage']['bot_manual_commits']:
    fmt_str += ' (%6.2f%% by humans)'
    data += (percentage(stats['usage']['cq_commits'],
                        stats['usage']['total_commits'] -
                        stats['usage']['bot_manual_commits']),)
  output(fmt_str, *data)

  output()
  output('Bots:                %6d out of %6d total committers %6.2f%%',
         *percentage_tuple(stats['usage']['bot_committers'],
                           stats['usage']['committers']))
  output('  Committed by CQ    %6d out of %6d commits          %6.2f%%',
         *percentage_tuple(stats['usage']['bot_commits'],
                           stats['usage']['total_commits']))
  output('  Committed directly %6d out of %6d commits          %6.2f%%',
         *percentage_tuple(stats['usage']['bot_manual_commits'],
                           stats['usage']['total_commits']))
  output()
  output('Manual committers: %6d out of all %6d users   %6.2f%%',
         *percentage_tuple(stats['usage']['manual_committers'],
                           stats['usage']['committers']))
  output('  Committed        %6d out of     %6d commits %6.2f%%',
         *percentage_tuple(stats['usage']['manual_commits'],
                           stats['usage']['total_commits']))


def print_tree_status(stats):
  output()
  output(
      'Total time tree open: %.1f hours of %.1f hours (%.2f%%). ',
      stats['tree']['open'] / 3600.0,
      stats['tree']['total'] / 3600.0,
      percentage(stats['tree']['open'], stats['tree']['total']))


def print_stats(args, stats):
  if not stats:
    output('No stats to display.')
    return
  output('Statistics for project %s', args.project)
  if stats['begin'] > stats['end']:
    output('  No stats since %s', args.date)
    return

  output('from %s till %s (local time).',
         stats['begin'], stats['end'])

  print_usage(stats)
  print_tree_status(stats)

  output()
  output(
      '%4d issues (%d patches) were tried by CQ, '
      'resulting in %d attempts.',
      stats['issue-count'], stats['patchset-count'], stats['attempt-count'])
  output(
      '%4d patches (%.1f%% of tried patches, %.1f%% of attempts) '
      'were committed by CQ,',
      stats['patchset-commit-count'],
      percentage(stats['patchset-commit-count'], stats['patchset-count']),
      percentage(stats['patchset-commit-count'], stats['attempt-count']))


  output()
  output('Rejections:')
  print_attempt_counts(stats, 'rejections', 'were unsuccessful',
                       item_name='failures',
                       committed=False)
  output('  This includes:')
  for reason in REASONS:
    print_attempt_counts(stats, reason, REASONS[reason]['message'], indent=2,
                         details=args.list_rejections,
                         item_name=REASONS[reason]['item'], committed=False)

  # TODO(sergeyberezin): add gave up count (committed manually after trying CQ).
  # TODO(sergeyberezin): add count of NOTRY=true (if possible).

  output()
  output('False Rejections:')
  if args.use_logs:
    print_attempt_counts(stats, 'false-rejections', 'were false rejections',
                         item_name='flakes', committed=True)
  else:
    output(
        '  %4d attempts (%.1f%% of %d attempts) were false rejections',
        stats['attempt-false-reject-count'],
        percentage(stats['attempt-false-reject-count'],
                   stats['attempt-count']),
        stats['attempt-count'])

  output('  False rejections include:')
  for reason in FLAKY_REASONS.keys() + ['failed-unknown']:
    print_attempt_counts(stats, reason, REASONS[reason]['message'], indent=2,
                         item_name=REASONS[reason]['item'], committed=True,
                         details=args.list_false_rejections)

  output('  Other rejections in committed patches for valid reasons:')
  for reason in VALID_REASONS.keys():
    print_attempt_counts(stats, reason, REASONS[reason]['message'], indent=2,
                         item_name=REASONS[reason]['item'], committed=True,
                         details=args.list_false_rejections)

  print_duration('mean', stats)
  print_duration('50', stats, 'Median')

  output()
  output('Patches which eventually land percentiles:')
  for p in ['10', '25', '50', '75', '90', '95', '99']:
    output('%s: %4.1f hrs, %2d attempts',
           p, stats['patchset-committed-durations'][p] / 3600.0,
           stats['patchset-committed-attempts'][p])

  output()
  output('Slowest CLs:')
  slowest_cls = sorted(
      stats['patch_stats'],
      key=lambda p: stats['patch_stats'][p]['patchset-duration'],
      reverse=True)
  for p in slowest_cls[:40]:
    output('%s (%s hrs)' % (
        patch_url(p),
        round(stats['patch_stats'][p]['patchset-duration'] / 3600.0, 1)))

  # TODO(sergeyberezin): add total try jobs / by CQ / unknown. Get it from CBE.
  # TODO(sergeyberezin): recompute bot flakiness from CBE. CQ does not
  # have enough info.
  output()
  output('Top flaky builders (which fail and succeed in the same patch):')

  logging.debug('Found %d jobs', len(stats['jobs'].keys()))

  def flakiness(job):
    passes = stats['jobs'][job]['pass-count']
    failures = stats['jobs'][job]['false-reject-count']
    return percentage(failures, passes + failures)

  jobs = sorted(stats['jobs'].iterkeys(), key=flakiness, reverse=True)
  job_spaces = reduce(max, map(len, jobs)) if jobs else 0
  output('%-' + str(job_spaces)  + 's %-15s %-15s %-15s',
         'Builder Name', 'Succeeded', 'Flaky Failures', 'Flakiness (%)')
  for job in jobs:
    passes = stats['jobs'][job]['pass-count']
    failures = stats['jobs'][job]['false-reject-count']
    output('%-' + str(job_spaces) + 's %-15s %-15s %-15s',
           job, '%5d' % passes, '%5d' % failures,
           '%6.2f%%' % flakiness(job))


def acquire_stats(args):
  stats = {}
  logging.info('Acquiring stats for project %s for a %s of %s using %s',
               args.project, args.range, args.date,
               'logs' if args.use_logs else 'cache')
  end_date = args.date + datetime.timedelta(minutes=INTERVALS[args.range])
  if args.use_logs:
    init_stats = default_stats()
    assert args.date
    # For weekly stats, collect job flakiness from daily cached stats.
    if args.range == 'week':
      for day in range(7):
        d = args.date + datetime.timedelta(minutes=INTERVALS['day']*day)
        raw_stats = fetch_stats(args, d, 'day')
        init_stats = organize_stats(raw_stats, init=init_stats)
    elif args.range == 'day':
      for hour in range(24):
        d = args.date + datetime.timedelta(minutes=INTERVALS['hour']*hour)
        raw_stats = fetch_stats(args, d, 'hour')
        init_stats = organize_stats(raw_stats, init=init_stats)
    else:
      init_stats = organize_stats(fetch_stats(args))
    stats = derive_stats(
        args, args.date, init_stats=init_stats)
  else:
    stats = organize_stats(fetch_stats(args))

  stats['tree'] = derive_tree_stats(args.project, args.date, end_date)

  if PROJECTS[args.project]['type'] == 'git':
    stats['usage'] = derive_git_stats(
        args.project, args.date, end_date, args.bots)
  else:
    stats['usage'] = derive_svn_stats(
        args.project, args.date, end_date, args.bots)

  return stats

def main():
  args = parse_args()
  logger = logging.getLogger()
  # TODO(sergeyberezin): how do I derive local timezone string?
  # Need to be able to pass dateutil.tz.tzlocal() directly.
  infra_libs.logs.process_argparse_options(args, logger)
  stats = acquire_stats(args)
  print_stats(args, stats)


if __name__ == '__main__':
  sys.exit(main())
