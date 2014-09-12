# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Measures the average time used by git-push command in CQ based on data from
chromium-cq-status.appspot.com."""

import argparse
import json
import logging
import sys
import urllib


CQ_STATUS_QUERY_URL = 'http://chromium-cq-status.appspot.com/query'


def load_options():
  parser = argparse.ArgumentParser(description=sys.modules['__main__'].__doc__)
  parser.add_argument('--project', default='chromium', help='Project name.')
  parser.add_argument('--count', '-c', default=1000, type=int, required=True,
                      help='Number of issues to average over.')
  parser.add_argument('--verbose', '-v', action='store_true',
                      help='Print debugging messages to console')
  return parser.parse_args()


def get_stats(filters, cursor=None):
  url = '%s/%s' % (CQ_STATUS_QUERY_URL, '/'.join(filters))
  if cursor:
    url += '?cursor=%s' % cursor
  logging.debug('Loading %s', url)
  data = json.load(urllib.urlopen(url))
  return data['results'], data['cursor'], data['more']


def main():
  options = load_options()
  filters = []
  if options.project:
    filters += ['project=%s' % options.project]

  logging.basicConfig(level=logging.DEBUG if options.verbose else logging.INFO,
                      format='%(asctime)s %(levelname)s %(message)s')

  # We search for committed timestamps first, because this guarantees that all
  # these issues will also have comitting timestamp. The opposite is not always
  # true - some issues with committing timestamp may not be comitted yet.
  logging.info('Searching for committed issues')
  issues = []
  cursor = None
  more = True
  while len(issues) < options.count and more:
    results, cursor, more = get_stats(filters + ['action=patch_committed'],
                                      cursor)
    for result in results:
      issues.append({'issue': result['fields']['issue'],
                     'patchset': result['fields']['patchset'],
                     'committed': result['fields']['timestamp']})

  if len(issues) > options.count:
    issues = issues[:options.count]

  logging.debug('Searching committing timestamp for found issues')
  for issue in issues:
    results, _, _ = get_stats(filters + ['action=patch_committing',
                                         'issue=%s' % issue['issue'],
                                         'patchset=%s' % issue['patchset']])
    assert len(results) >= 1, 'Incorrect number of results: %s' % results
    issue['committing'] = results[0]['fields']['timestamp']

  logging.debug(issues)
  push_times = [i['committed'] - i['committing'] for i in issues]
  average_push_time = sum(push_times) / len(push_times)

  print 'Average git push time is %.2f seconds' % average_push_time


if __name__ == '__main__':
  sys.exit(main())
