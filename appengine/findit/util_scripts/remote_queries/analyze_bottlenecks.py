# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Analyze WfAnalysis entities and their pipelines/tryjobs/swarmjobs.

This works on locally available pickled objects pulled via bottleneck_query.py

The purpose of the analysis this script performs is to locate the parts of the
process that have the biggest impact in the total turnaround time for successful
analyses, so that the process can be streamlined.
"""

import csv
import datetime
import json
import os
import pickle
import re
import sys
import time

from collections import defaultdict
import matplotlib.pyplot as plt
import numpy
import optparse

_APPENGINE_SDK_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir,
                                  os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir,
                                  'google_appengine')
sys.path.insert(1, _APPENGINE_SDK_DIR)
from google.appengine.ext import ndb

_REMOTE_API_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir)
sys.path.insert(1, _REMOTE_API_DIR)
import remote_api
from model.wf_analysis import WfAnalysis


# Global stats
all_labels = set()
by_status = defaultdict(int)
by_failure = defaultdict(int)


class _Coalesce(object):
  """Replace variable elements in event labels.

  Replaces hashes with <hash>, test names with <test>, builder names with
  <builder>, etc. Also keeps track of all the labels produced via an external
  set().

  Args:
    label: A string representing the name of a timed event.
  Returns:
    a string with the appropriate replacements.
  """
  def __init__(self, options):
    self.options = options

  def __call__(self, label):
    # TODO(coalesce buildernames)
    options = self.options
    hash_re = '[a-fA-F0-9]{40}'

    result = label
    # _Coalesce hashes
    if options.coalesce_hashes:
      result = re.sub(hash_re, '<hash>', result)

    # _Coalesce test names
    if options.coalesce_tests:
      dot_sep = result.split('.')
      if len(dot_sep) > 1:
        test_name = dot_sep[1].split()[0]
        if test_name.endswith('tests'):
          result = result.replace(test_name, '<tests>')

    # coalesce all but ends
    if options.coalesce_middle:
      dot_sep = result.split('.')
      if len(dot_sep) > 2:
        result = '.'.join([dot_sep[0], '*', dot_sep[-2], dot_sep[-1]])

    all_labels.add(result)
    return result


def _LoadFilterAndSortRecords(options):
  loaded_records = pickle.load(open('records.pickle'))
  sorted_records = []
  # Parse filter options
  if options.result_status != 'all':
    allowed_statuses = map(int, options.result_status.split(','))
  if options.failure_type != 'all':
    allowed_failure_types = map(int, options.failure_type.split(','))

  # go over all records
  for k, v in loaded_records.iteritems():
    # Filter by Status and FailureType
    if options.result_status != 'all' and (
        v['wfa.result_status'] not in allowed_statuses):
      continue
    if options.failure_type != 'all' and (
        v['wfa.build_failure_type'] not in allowed_failure_types):
      continue

    # Exclude android records
    if options.exclude_android:
      if 'ndroid' in k.pairs()[0][1]:
        continue
    # Filter masters
    if options.allowed_masters:
      m = k.pairs()[0][1].split('/')[0]
      if m not in options.allowed_masters.split(','):
        continue

    # Filter by date
    if options.before_date:
      cutoff = datetime.datetime(
          *time.strptime(options.before_date, '%Y-%m-%d')[:6])
      if v['wfa.request_time'] > cutoff:

        continue
    if options.after_date:
      cutoff = datetime.datetime(
          *time.strptime(options.after_date, '%Y-%m-%d')[:6])
      if v['wfa.request_time'] < cutoff:
        continue
    sorted_record = []
    for label, t in v.iteritems():
      if isinstance(t, datetime.datetime):
        sorted_record.append((t, label))
      else:
        if label == 'wfa.result_status':
          by_status[t] += 1
        if label == 'wfa.build_failure_type':
          by_failure[t] += 1
    # Sort by ts
    sorted_record.sort()

    # Filter events that occur before a specific events
    if options.after_label:
      result = []
      copy_all = False
      for x in sorted_record:
        if copy_all or x[1] == options.after_label:
          copy_all = True
          result.append(x)
      sorted_record = result
    sorted_records.append((sorted_record, k))
  return sorted_records, loaded_records


def _SummarizeRecordPaired(loaded_records, coalesce, record, k, transitions,
                           adjacent, examples, totals):
  # Considers transitions as the difference between events A.start and A.end as
  # well as events that are immediately one after the other (adjacent). This
  # applies to every pair of events in the record.
  for i in range(len(record) -1):
    label_pair = None
    if record[i][1].endswith('.start'):
      # Search for the matching .end label
      label_pair = record[i][1], record[i][1].replace('.start', '.end')
      transition = tuple(map(coalesce, label_pair))
      if label_pair[1] in loaded_records[k].keys():
        start = loaded_records[k][label_pair[0]]
        end = loaded_records[k][label_pair[1]] or datetime.datetime(
            2010, 1, 1)
        interval = (end - start).total_seconds()
        if interval > 0:
          # NB: Silently ignoring negative intervals.
          if transition not in transitions or interval > max(
              transitions[transition]):
            examples[transition] = k, record
          totals[transition] += interval
          transitions[transition].append(interval)
    neighbor_labels = (record[i][1], record[i + 1][1])
    transition = tuple(map(coalesce, neighbor_labels))
    # if x.start and x.end are adjacent)
    if label_pair == neighbor_labels:
      adjacent[transition] += 1
      continue
    start = record[i][0]
    end = record[i + 1][0]
    if (isinstance(start, datetime.datetime) and
        isinstance(end, datetime.datetime)):
      interval = (end - start).total_seconds()
      adjacent[transition] += 1
      transitions[transition].append(interval)
      # Record the example that takes the longest.
      if transition not in examples.keys() or interval > max(
          transitions[transition]):
        examples[transition] = k, record
      totals[transition] += interval


def _SummarizeRecordCustom(from_regex, to_regex):
  # Considers transitions as the difference between events matching from_regex
  # to to_regex, only once per record.
  def inner(loaded_records, coalesce, record, k, transitions,
            adjacent, examples, totals):
    start_index = 0
    for i in range(len(record)):
      if from_regex.match(record[i][1]):
        start_index = i
      elif to_regex.match(record[i][1]) and start_index:
        label_pair = record[start_index][1], record[i][1]
        transition = tuple(map(coalesce, label_pair))
        start = loaded_records[k][label_pair[0]]
        end = loaded_records[k][label_pair[1]] or datetime.datetime(
            2010, 1, 1)
        interval = (end - start).total_seconds()
        if interval > 0:
          # NB: Silently ignoring negative intervals.
          if transition not in transitions or interval > max(
              transitions[transition]):
            examples[transition] = k, record
          totals[transition] += interval
          transitions[transition].append(interval)
          if i == start_index + 1:
            adjacent[transition] += 1
          break
  return inner


def _AggregateTransitions(options, sorted_records, loaded_records):
  summarize_func = _SummarizeRecordPaired
  if options.swarming_latency:
    options.coalesce_middle = True
    options.paired_only = False
    options.min_transition_count = 1
    options.show_composites = True
    summarize_func = _SummarizeRecordCustom(
      from_regex=re.compile(r'pl\.Trigger.*SwarmingTaskPipeline\.start'),
      to_regex=re.compile(r'swarm.*started_ts')
    )
  elif options.tryjob_latency:
    options.coalesce_middle = True
    options.paired_only = False
    options.min_transition_count = 1
    options.show_composites = True
    summarize_func = _SummarizeRecordCustom(
      from_regex=re.compile(r'pl\.Schedule.*TryJobPipeline\.start'),
      to_regex=re.compile(r'try\..*\.steps\.start')
    )
  coalesce = _Coalesce(options)
  transitions = defaultdict(list)
  adjacent = defaultdict(int)
  examples = {}
  totals = defaultdict(float)
  for record, k in sorted_records:
    summarize_func(loaded_records, coalesce, record, k, transitions, adjacent,
                   examples, totals)
  return _StatsForTransitions(options, transitions, totals, adjacent, examples,
                              sorted_records)


def _StatsForTransitions(options, transitions, totals, adjacent, examples,
                         sorted_records):
  result = []
  for transition, t in transitions.iteritems():
    current = {
        'median': numpy.percentile(t, 50),
        '90p': numpy.percentile(t, 90),
        'max': max(t),
        'count': len(t),
        'transition': transition,
        'total_time': totals[transition],
        'adjacent_count': adjacent[transition],
    }
    if options.raw_values_only:
      current = {
          'values': t,
          'transition': transition,
      }
    if options.example:
      current['example'] = examples[transition]
    result.append(current)

  if options.output_format == 'text':
    print 'Processed %d analyses' % len(sorted_records)

  return result


def PrintCsv(dict_list):
  columns = dict_list[0].keys()
  # de-nest
  for d in dict_list:
    _from, _to = d.get('transition', ('', ''))
    d['transition_from'] = _from
    d['transition_to'] = _to
    del(d['transition'])
  columns.remove('transition')
  columns = ['transition_from', 'transition_to'] + columns
  writer = csv.DictWriter(sys.stdout, columns)
  writer.writeheader()
  for d in dict_list:
    writer.writerow(d)


def _MaybePrintRow(r, options):
  """Prints a row to the console if not filtered.

  This display function decides whether to print a row to stdout and returns
  a bool indicating whether it displayed it."""

  if options.label_filter and options.label_filter not in ''.join(
      r['transition']):
    return False
  _from, _to = r['transition']
  if _from.replace('.start', '.end') == _to:
    r['transition_text'] = _from.replace('.start', '')
  else:
    if options.paired_only:
      return False
    r['transition_text'] = '%s -> %s' % (_from, _to)
  if options.raw_values_only:
    print r['transition_text'], r['values']
    plt.hist(r['values'])
    plt.title(r['transition_text'])
    plt.show()
  else:
    if not options.show_composites and not r['adjacent_count']:
      return False
    r['adjacent_percentage'] = r['adjacent_count'] * 100 / r['count']
    r['mean'] = r['total_time'] / r['count']
    print ('%(transition_text)s:\n'
           '\tn: %(count)d, median: %(median)0.2fs, mean: %(mean)0.2fs, '
           '90p: %(90p)0.2fs, Max: '
           '%(max)0.2fs, Total: %(total_time)0.2fs, '
           'Adj.: %(adjacent_percentage)d%%' % r)

  # Show example analysis time series.
  if options.example:
    print r['example'][0]
    for ts, event in r['example'][1]:
      print '\t', str(ts), event
  return True


def _ParseOptions():
  usage = """usage: %prog [options]

Analyze the times of the wf_Analysis objects pickled locally via
bottleneck_query.py

From each Wf_Analysis object all timestamps are extracted, including associated
pipelines, swarming tasks and tryjobs.

These records are filtered, coalesced and aggregated as per the options below
and the summarized data is output as text, json or csv.
"""
  parser = optparse.OptionParser(usage=usage)

  # Pre-aggregation filters
  pre_aggregation = optparse.OptionGroup(parser, 'Pre-aggregation filters')

  pre_aggregation.add_option('-r', '--result_status', default='30', help='Comma'
                             '-separated list of statuses from findit/model/'
                             'result_status.py(e.g. 30 for FOUND_UNTRIAGED) or'
                             ' "all" for any status.')
  pre_aggregation.add_option('-f', '--failure_type', default='8,16',
                             help='Comma-separated list of failure types from '
                             'findit/common/waterfall/failure_type.py (default:'
                             '"8,16" i.e. Reliable compile and test failures)')
  pre_aggregation.add_option('--after_label', help='Only aggregate events'
                             ' that happen after this label. E.g. request_time.'
                             ' Used to exclude events occurring before findit'
                             ' is informed of the failure, for example.')

  pre_aggregation.add_option('-b', '--before_date', help='A date in format '
                             'YYYY-mm-dd used to filter jobs that are too '
                             'recent and may be in progress. NB the data'
                             ' is retrieved using a separate script with its '
                             'own set of filters, this acts in addition to'
                             ' those.')
  pre_aggregation.add_option('-a', '--after_date', help='A date in format '
                             'YYYY-mm-dd used to filter jobs that are too '
                             'old. NB the data is retrieved using a separate '
                             'script with its own set of filters, this acts in '
                             'addition to those.')
  pre_aggregation.add_option('--exclude_android', action='store_true', help=
                             'exclude records for android platforms')
  pre_aggregation.add_option('--allowed_masters', default='', help='Comma'
                             '-separated list of masters to include. Include '
                             'all if not specified.')
  pre_aggregation.add_option('--swarming_latency', action='store_true',
                             help='Canned query to measure the time it takes '
                             'for a swarming task to start from the moment it '
                             ' is requested.')
  pre_aggregation.add_option('--tryjob_latency', action='store_true',
                             help='Canned query to measure the time it takes '
                             'for a try job to start from the moment it '
                             ' is requested.')
  parser.add_option_group(pre_aggregation)

  # Coalescing options
  coalesce_opts = optparse.OptionGroup(parser, 'Coalescing options', 'By '
                                       'default hashes are converted to <hash> '
                                       'and test steps are converted to <tests>'
                                       ' e.g brower_tests and net_unittests are'
                                       ' both replaced by <tests>.')

  coalesce_opts.add_option('--no_coalesce_tests', action='store_false',
                           dest='coalesce_tests', default=True, help='Use this'
                           ' flag to group the times for different tests'
                           ' separately.')
  coalesce_opts.add_option('--no_coalesce_hashes', action='store_false',
                           dest='coalesce_hashes', default=True, help='Use '
                           'this flag to separate steps by revision.')
  coalesce_opts.add_option('--coalesce_middle', action='store_true',
                           default=False, help='Take into account only the '
                           'first and last parts of the label. e.g. '
                           'try.compile.bot_update and '
                           'try.test <hash>.bot_update both become '
                           'try.*.bot_update')

  parser.add_option_group(coalesce_opts)


  # Post-aggregation Filters
  post_aggregation = optparse.OptionGroup(
      parser, 'Text mode filters', 'Apply the following after the records have'
      ' been aggregated.')
  post_aggregation.add_option('--plot', action='store_true',
                              dest='raw_values_only', default=False,
                              help='Display the values of the intervals instead'
                              ' of computed statistics.')
  post_aggregation.add_option(
      '-o', '--sort', type='str', default='-median', help='Sort the results '
      'by one of the following fields (prepend with - to reverse order): '
      'median(default), 90p, max, count, transition, total_time, or '
      'adjacent_count.')
  post_aggregation.add_option('-t', '--top', type='int', default=100,
                              help='How many rows to display.')
  post_aggregation.add_option('-l', '--label_filter', help='Only display '
                              'transitions containing the given string.')
  post_aggregation.add_option('-m', '--min_transition_count', type='int',
                              default=10, help='Exclude transitions that occur '
                              'fewer than this many times (default: 10)')
  post_aggregation.add_option('-u', '--show-unpaired', action='store_false',
                              dest='paired_only', default=True, help='Display '
                              'transitions not matching the form "x.start -> '
                              'x.end".')
  post_aggregation.add_option('-c', '--show_composites', action='store_true',
                              help='Show transitions of the form "x.start -> '
                              'x.end" that always contain events in the middle.'
                              )
  post_aggregation.add_option(
      '-x', '--example', action='store_true', help='Display one whole record '
      'that contains each transition. Useful for debugging.')
  parser.add_option_group(post_aggregation)


  # Display options
  display_opts = optparse.OptionGroup(parser, 'Output format options', 'Choose'
                                      ' one of json/csv/text(default)/none.')

  display_opts.add_option('--json', dest='output_format', action='store_const',
                    const='json', help='Dump data as JSON to STDOUT.')
  display_opts.add_option('--csv', dest='output_format', action='store_const',
                          const='csv', help='Produce a comma-separated values '
                          'file (with header row) and dump to STDOUT.')
  display_opts.add_option('--text', dest='output_format', action='store_const',
                          const='text', default='text', help='Apply text mode '
                          'filters and display results in the console.')
  display_opts.add_option('--none', dest='output_format', action='store_const',
                          const='none', help='Do not display results (e.g. if '
                          'only global stats are of interest)')
  parser.add_option_group(display_opts)

  # Global stats display
  #TODO: not supported if json or csv
  global_stats = optparse.OptionGroup(
      parser, 'Global stats display', 'Display certain stats regarding all '
      'locally pickled records if display mode is --text or --none.')

  global_stats.add_option('--all_globals', action='store_true', help='Implies '
                          'the following:')
  global_stats.add_option('--status_counts', action='store_true')
  global_stats.add_option('--failure_counts', action='store_true')
  global_stats.add_option('--label_count', action='store_true')
  parser.add_option_group(global_stats)

  options, _ = parser.parse_args()

  # Options validation
  if options.output_format in ['csv', 'json'] and options.example:
    options.example = False

  return options


def main():
  options = _ParseOptions()

  # Results
  aggregated_transitions = _AggregateTransitions(options,
      *_LoadFilterAndSortRecords(options))

  if options.raw_values_only:
    aggregated_transitions = [x for x in aggregated_transitions
                              if any(x['values'])]
  else:
    # Filter out short transitions (< 0.1 seconds) and uncommon transitions.
    aggregated_transitions = [
        x for x in aggregated_transitions
        if x['count'] >= options.min_transition_count and x['median'] > 0.1]

    # Sort transition aggregates
    key = options.sort
    reverse = False
    if key.startswith('-'):
      key = key[1:]
      reverse = True
    aggregated_transitions.sort(key=lambda x: x[key], reverse=reverse)

  if options.output_format == 'text':
    # assemble <options.top> rows of results
    result_count = options.top
    for r in aggregated_transitions:
      if _MaybePrintRow(r, options):
        result_count -= 1
      if not result_count:
        break
  elif options.output_format == 'json':
    print json.dumps(aggregated_transitions, indent=4)
  elif options.output_format == 'csv':
    PrintCsv(aggregated_transitions)

  # Show global stats
  if options.output_format not in ['csv', 'json']:
    if options.status_counts or options.all_globals:
      print 'Counts by status:', dict(by_status)
    if options.failure_counts or options.all_globals:
      print 'Counts by failure type:', dict(by_failure)
    if options.label_count or options.all_globals:
      print len(all_labels), 'different labels found'


if __name__ == '__main__':
  main()
