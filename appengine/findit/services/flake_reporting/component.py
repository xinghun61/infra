import datetime

from google.appengine.ext import ndb

from libs import time_util
from model.flake.detection.flake_occurrence import \
    CQFalseRejectionFlakeOccurrence as Occurrence
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TestFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport


class ReportExistsException(Exception):
  pass


def Report(year, week_number):
  """Creates report data for a given week.

  Iterates over flake occurrences detected in the given week, accumulates counts
  of occurrences, distinct tests and distinct cls for a given component; and
  occurrences and distinct cls for a given component/test combination.

  After the totals are accummulated, persists the entities to datastore.

  Args:
    year, week_number (int): Date in ISO week format
        https://en.wikipedia.org/wiki/ISO_week_date
        Note that the report includes occurrences detected from Monday 00:00
        PST of the given week.
  """
  if TotalFlakinessReport.Get(year, week_number):
    raise ReportExistsException(
        'Report already exist for %d-W%02d' % (year, week_number))

  # Data structure to accumulate the counts in.
  counters = _NewTally(TotalFlakinessReport.MakeId(year, week_number))
  # After tallying, should look something like this:
  # {
  #   '_id': '2018-W23',
  #   # Totals
  #   '_cq_false_rejection_occurrences': 100,
  #   '_tests': set(['test1', ...]),
  #   '_cls': set([12345, 12346, 12348, ...]),
  #   'component1': {
  #     # Per-component Totals
  #     '_id': 'component1',
  #     '_cq_false_rejection_occurrences': 10,
  #     '_tests': set(['test1', ...]),
  #     '_cls': set([12345, 12348, ...),
  #     'test1': {
  #       # Per-(component/test) Totals
  #       '_id': 'test1',
  #       '_cq_false_rejection_occurrences': 2,
  #       '_cls': set([12345]),
  #     }, ...<more tests>
  #   }, ...<more components>
  # }

  start = time_util.ConvertISOWeekToUTCDatetime(year, week_number)
  end = start + datetime.timedelta(days=7)
  query = Occurrence.query(
      ndb.AND(Occurrence.time_happened >= start,
              Occurrence.time_happened < end))

  cursor = None
  more = True
  while more:
    occurrences, cursor, more = query.fetch_page(500, start_cursor=cursor)
    for occurrence in occurrences:
      _CountOccurrence(occurrence, counters)
  _SaveReportToDatastore(counters)


def _NewTally(id_string):
  return {
      '_id': id_string,
      '_cq_false_rejection_occurrences': 0,
      '_tests': set(),
      '_cls': set()
  }


def _AddToTally(tally, test, cl):
  tally['_cq_false_rejection_occurrences'] += 1
  tally['_tests'].add(test)
  tally['_cls'].add(cl)


def _CountOccurrence(occurrence, counters):
  flake = occurrence.key.parent().get()
  component = flake.component or 'Unknown'
  test = flake.normalized_test_name
  cl = occurrence.gerrit_cl_id

  _AddToTally(counters, test, cl)

  if component not in counters:
    counters[component] = _NewTally(component)
  _AddToTally(counters[component], test, cl)

  if test not in counters[component]:
    counters[component][test] = _NewTally(test)
  _AddToTally(counters[component][test], test, cl)


def _SaveReportToDatastore(counters):
  # The entities to persist.
  entities = []
  report = TotalFlakinessReport.FromTallies(None, counters)
  entities.append(report)
  for component, c_counters in counters.iteritems():
    if component.startswith('_'):
      continue
    component_row = ComponentFlakinessReport.FromTallies(report.key, c_counters)
    entities.append(component_row)
    for test, t_counters in c_counters.iteritems():
      if test.startswith('_'):
        continue
      entities.append(
          TestFlakinessReport.FromTallies(component_row.key, t_counters))
  ndb.transaction(lambda: ndb.put_multi(entities))
