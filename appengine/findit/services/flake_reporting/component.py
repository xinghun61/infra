import datetime

from google.appengine.ext import ndb

from libs import time_util
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
from model.flake.reporting.report import ComponentFlakinessReport
from model.flake.reporting.report import TestFlakinessReport
from model.flake.reporting.report import TotalFlakinessReport
from services.constants import DAYS_IN_A_WEEK
from services.constants import DEFAULT_LUCI_PROJECT


class ReportExistsException(Exception):
  pass


def Report(save_test_report=False):
  """Creates report data for a given week.

  Iterates over flakes have happened in the week, and adds information we can
    directly get from flakes (component, test name, occurrences_counts in the
    week) to the counters.

  Then iterates all flake occurrences happened in the week (using projection
    query to lower latency and cost) to count distinct impacted CLs.

  After the totals are accummulated, persists the entities to datastore.

  Args:
    save_test_report (bool): True if save TestFlakinessReport entries, otherwise
      False. Noted: an error "too much contention on these datastore entities"
      may fire when also save TestFlakinessReport entries.
  """
  report_date = time_util.GetMidnight(
      time_util.GetDateDaysBeforeNow(days=DAYS_IN_A_WEEK))
  if TotalFlakinessReport.Get(report_date, DEFAULT_LUCI_PROJECT):
    raise ReportExistsException('Report already exist for {}'.format(
        time_util.FormatDatetime(report_date, day_only=True)))

  # TODO(crbug.com/920926): Use classes instead of a big dict for temp data.
  # Data structure to accumulate the counts in.
  # After tallying, should look something like this:
  # {
  #   'chromium': {
  #     '_id': '2018-08-27',
  #     # Totals
  #     '_bugs': set([FlakeIssue.key, ...]),
  #     '_impacted_cls': {
  #         FlakeType.CQ_FALSE_REJECTION: set([12345, 12346, ...]),
  #         FlakeType.RETRY_WITH_PATCH: set([12348, ...])
  #     },
  #     '_occurrences': {
  #         FlakeType.CQ_FALSE_REJECTION: 100,
  #         FlakeType.RETRY_WITH_PATCH: 1800},
  #     '_tests': set(['test1', ...]),
  #     'component1': {
  #       # Per-component Totals
  #       '_id': 'component1',
  #       '_bugs': set([FlakeIssue.key, ...]),
  #       '_impacted_cls': {
  #           FlakeType.CQ_FALSE_REJECTION: set([12345, 12346, ...]),
  #           FlakeType.RETRY_WITH_PATCH: set([12348, ...])
  #       },
  #       '_occurrences': {
  #           FlakeType.CQ_FALSE_REJECTION: 10,
  #           FlakeType.RETRY_WITH_PATCH: 100},
  #       '_tests': set(['test1', ...]),
  #       'test1': {
  #         # Per-(component/test) Totals
  #         '_id': 'test1',
  #         '_bugs': set([FlakeIssue.key, ...]),
  #         '_impacted_cls': {
  #             FlakeType.CQ_FALSE_REJECTION: set([12345]),
  #             FlakeType.RETRY_WITH_PATCH: set([12348])
  #         },
  #         '_occurrences': {
  #           FlakeType.CQ_FALSE_REJECTION: 1,
  #           FlakeType.RETRY_WITH_PATCH: 18},
  #         '_tests': set(['test1']),
  #       }, ...<more tests>
  #     }, ...<more components>
  #   },
  #   ... <more project>
  # }
  counters = {}

  # A dict with key as each flake's ndb key and value as each flake's component
  # and normalized_test_name.
  flake_info_dict = {}

  end = report_date + datetime.timedelta(days=7)

  _AddFlakesToCounters(counters, flake_info_dict, report_date, save_test_report)
  _AddDistinctCLsToCounters(counters, flake_info_dict, report_date, end,
                            save_test_report)
  SaveReportToDatastore(counters, report_date, save_test_report)


def _NewTally(id_string):
  tally = {
      '_id': id_string,
      '_bugs': set(),
      '_impacted_cls': {},
      '_occurrences': {},
      '_tests': set()
  }

  for flake_type in FLAKE_TYPE_DESCRIPTIONS:
    tally['_impacted_cls'][flake_type] = set()
    tally['_occurrences'][flake_type] = 0

  return tally


def _AddFlakeToTally(tally, flake):
  tally['_bugs'].add(flake.GetIssue(up_to_date=True, key_only=True))
  tally['_tests'].add(flake.normalized_test_name)
  for flake_count in flake.flake_counts_last_week:
    tally['_occurrences'][flake_count
                          .flake_type] += flake_count.occurrence_count


def _AddFlakesToCounters(counters, flake_info_dict, start, save_test_report):
  """Queries all flakes that have happened after start time and adds their info
    to counters.
  """
  query = Flake.query()
  query = query.filter(Flake.last_occurred_time >= start)

  cursor = None
  more = True
  while more:
    flakes, cursor, more = query.fetch_page(500, start_cursor=cursor)
    for flake in flakes:
      luci_project = flake.luci_project
      if luci_project not in counters:
        counters[luci_project] = _NewTally(
            TotalFlakinessReport.MakeId(start, luci_project))
      _AddFlakeToTally(counters[luci_project], flake)

      component = flake.GetComponent()
      test = flake.normalized_test_name
      flake_info_dict[flake.key] = {
          'luci_project': luci_project,
          'component': component,
          'test': test
      }

      if component not in counters[luci_project]:
        counters[luci_project][component] = _NewTally(component)
      _AddFlakeToTally(counters[luci_project][component], flake)

      if save_test_report:  # pragma: no branch.
        if test not in counters[luci_project][component]:
          counters[luci_project][component][test] = _NewTally(test)
        _AddFlakeToTally(counters[luci_project][component][test], flake)


def _UpdateDuplicatedClsBetweenTypes(counters):
  """Updates the _impacted_cls values in counters to make sure no duplicated CLs
    between flake types.

    For example, if CL 12345 was affected by both CQ_FALSE_REJECTION and
      RETRY_WITH_PATH flakes, only keeps it in CQ_FALSE_REJECTION.

    This is to make sure counts are consistent in the report and in Flake
      Detection dashboard.
  """

  def UpdateTallyCLs(tally):
    counted_impacted_cls = set()

    # Assumes flake_type with bigger value has lower impact.
    # Removes duplicated CLs from flake_type with lower impact.
    for flake_type in sorted(FLAKE_TYPE_DESCRIPTIONS):
      tally['_impacted_cls'][flake_type] -= counted_impacted_cls
      counted_impacted_cls.update(tally['_impacted_cls'][flake_type])

  for p_counters in counters.values():
    UpdateTallyCLs(p_counters)
    for component, c_counters in p_counters.iteritems():
      if component.startswith('_'):
        continue
      UpdateTallyCLs(c_counters)
      for test, t_counters in c_counters.iteritems():
        if test.startswith('_'):
          continue
        UpdateTallyCLs(t_counters)


def _AddDistinctCLsToCounters(counters, flake_info_dict, start, end,
                              save_test_report):
  occurrences_query = FlakeOccurrence.query(
      projection=[FlakeOccurrence.flake_type, FlakeOccurrence.gerrit_cl_id
                 ]).filter(
                     ndb.AND(FlakeOccurrence.time_happened >= start,
                             FlakeOccurrence.time_happened < end))

  cursor = None
  more = True
  while more:
    occurrences, cursor, more = occurrences_query.fetch_page(
        500, start_cursor=cursor)

    for occurrence in occurrences:
      flake_key = occurrence.key.parent()
      luci_project = flake_info_dict.get(flake_key, {}).get('luci_project')
      component = flake_info_dict.get(flake_key, {}).get('component')
      test = flake_info_dict.get(flake_key, {}).get('test')

      # Broken data, bails out on this occurrence.
      if not luci_project or not counters.get(luci_project):
        continue
      if not component or not counters[luci_project].get(component):
        continue
      if save_test_report and (not test or
                               not counters[luci_project][component].get(test)):
        continue

      flake_type = occurrence.flake_type
      cl = occurrence.gerrit_cl_id
      counters[luci_project]['_impacted_cls'][flake_type].add(cl)
      counters[luci_project][component]['_impacted_cls'][flake_type].add(cl)
      if save_test_report:
        counters[luci_project][component][test]['_impacted_cls'][
            flake_type].add(cl)

  _UpdateDuplicatedClsBetweenTypes(counters)


def SaveReportToDatastore(counters, report_date, save_test_report=False):
  # The entities to persist.
  entities = []
  for luci_project, p_counters in counters.iteritems():
    project_tag = ('luci_project', luci_project)
    report = TotalFlakinessReport.FromTallies(
        None, p_counters, report_date, additional_tags=[project_tag])
    entities.append(report)
    for component, c_counters in p_counters.iteritems():
      if component.startswith('_'):
        continue
      component_tag = ('component', component)
      component_row = ComponentFlakinessReport.FromTallies(
          report.key,
          c_counters,
          report_date,
          additional_tags=[project_tag, component_tag])
      entities.append(component_row)
      if not save_test_report:
        continue
      for test, t_counters in c_counters.iteritems():
        if test.startswith('_'):
          continue
        test_tag = ('test', test)
        entities.append(
            TestFlakinessReport.FromTallies(
                component_row.key,
                t_counters,
                report_date,
                additional_tags=[project_tag, component_tag, test_tag]))

  ndb.put_multi(entities)
