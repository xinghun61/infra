import os
import sys

# Append paths so that dependencies would work.
_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
_THIRD_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
_FIRST_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'first_party')
sys.path.insert(0, _FINDIT_DIR)
sys.path.insert(0, _THIRD_PARTY_DIR)
sys.path.insert(0, _FIRST_PARTY_DIR)

# Activate script as findit prod.
from local_libs import remote_api
remote_api.EnableFinditRemoteApi()

# Add imports below.
import datetime
import textwrap

from libs import analysis_status
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from services import bigquery_helper


class FlakeAnalyzerReport(object):
  """Encapsulates an in-depth flake analyzer report for one week."""

  _METRICS_QUERY = textwrap.dedent("""
    select
      count(*) as number_of_analyses,
      sum(
        case when analysis_info.culprit.revision is not null
          then 1
          else 0
        end
      ) as number_of_culprits,
      avg(
        regression_range_confidence
      ) as average_regression_range_confidence,
      avg(
        case when analysis_info.culprit.revision is not null
          then analysis_info.culprit.confidence
          else null
        end
      ) as average_culprit_confidence,
      sum(
        case when array_to_string(analysis_info.actions, ' ') != ''
          then 1
          else 0
        end
      ) as number_of_autoactions_taken,
      sum(
        case when array_to_string(analysis_info.actions, ' ') \
        like '%BUG_CREATED%'
          then 1
          else 0
        end
      ) as number_of_bugs_filed,
      sum(
        case when array_to_string(analysis_info.actions, ' ') \
        like '%BUG_COMMENTED%'
          then 1
          else 0
        end
      ) as number_of_bugs_commented,
      sum(
        case when array_to_string(analysis_info.actions, ' ') \
        like '%CL_COMMENTED%'
          then 1
          else 0
        end
      ) as number_of_cls_commented
    from
      `findit-for-me.events.test`
    where
      # Analyses completed in the past day.
      analysis_info.timestamp.completed >=
        timestamp_sub(current_timestamp(), interval {end_days_back} day)
      and analysis_info.timestamp.completed <
        timestamp_sub(current_timestamp(), interval {start_days_back} day)
      # Flake analyses.
      and flake = true
  """)

  _TEMPLATE_STRING = textwrap.dedent("""
    Flake Analyzer Stats for this past week {week_start} though {week_end}:
    Total analyses: {number_of_analyses} ({number_of_analyses_dx})
    Regression range error rate: {rr_error_rate}% ({rr_error_rate_dx})
    Total culprits: {number_of_culprits} ({number_of_culprits_dx})
    Culprit analysis error rate: {ca_error_rate}% ({ca_error_rate_dx})
    Total auto-actions taken: {number_of_autoactions_taken} \
    ({number_of_autoactions_taken_dx})
    Total number of bugs filed: {number_of_bugs_filed} \
    ({number_of_bugs_filed_dx})
    Total number of bugs commented: {number_of_bugs_commented} \
    ({number_of_bugs_commented_dx})
    Total number of CLs commented: {number_of_cls_commented} \
    ({number_of_cls_commented_dx})
  """)

  _TEMPLATE_STRING_NO_CHANGE = textwrap.dedent("""
    Flake Analyzer Stats for the week {week_start} though {week_end}:
    Total analyses: {number_of_analyses}
    Regression range error rate: {rr_error_rate}%
    Total culprits: {number_of_culprits}
    Culprit analysis error rate: {ca_error_rate}%
    Total auto-actions taken: {number_of_autoactions_taken}
    Total number of bugs filed: {number_of_bugs_filed}
    Total number of bugs commented: {number_of_bugs_commented}
    Total number of CLs commented: {number_of_cls_commented}
  """)

  def __init__(self, start_days_back, display_change=True):
    self._display_change = display_change
    self._week_start = (
        datetime.datetime.now() - datetime.timedelta(days=start_days_back) -
        datetime.timedelta(days=7))

    # Ordered aggregate data from newest --> oldest.
    self._query_results = [
        bigquery_helper.ExecuteQuery(
            'findit-for-me',
            FlakeAnalyzerReport._METRICS_QUERY.format(
                start_days_back=start_days_back,
                end_days_back=start_days_back + 7))[1][0],
        bigquery_helper.ExecuteQuery(
            'findit-for-me',
            FlakeAnalyzerReport._METRICS_QUERY.format(
                start_days_back=start_days_back + 7,
                end_days_back=start_days_back + 14))[1][0],
    ]

    # Ordered error rates data from newest --> oldest.
    self._error_rates = [
        self._GetErrorRates(start_days_back, start_days_back + 7),
        self._GetErrorRates(start_days_back + 7, start_days_back + 14),
    ]

  def _GetAllAnalyses(self, start_days_back, end_days_back, PAGE_SIZE=500):
    """Get all the analyses within the day range."""
    start = datetime.datetime.now() - datetime.timedelta(days=start_days_back)
    end = datetime.datetime.now() - datetime.timedelta(days=end_days_back)

    all_analyses = []

    cursor = None
    more = True

    while more:
      query = MasterFlakeAnalysis.query(
          MasterFlakeAnalysis.request_time >= end,
          MasterFlakeAnalysis.request_time < start)
      analyses, cursor, more = query.fetch_page(PAGE_SIZE, start_cursor=cursor)
      all_analyses.extend(analyses)

    return all_analyses

  def _GetErrorRates(self, start_days_back, end_days_back):
    """Get the error rate within the day range."""
    flake_analyses = self._GetAllAnalyses(start_days_back, end_days_back)

    total_regression_analyses = 0
    regression_analysis_errors = 0
    total_culprit_analyses = 0
    culprit_analysis_errors = 0

    for analysis in flake_analyses:
      if analysis.status != analysis_status.SKIPPED:
        total_regression_analyses += 1
      if analysis.status == analysis_status.ERROR:
        regression_analysis_errors += 1

      if analysis.try_job_status != analysis_status.SKIPPED:
        total_culprit_analyses += 1
      if analysis.try_job_status == analysis_status.ERROR:
        culprit_analysis_errors += 1

    ra_error_rate = (
        float(regression_analysis_errors) / float(total_regression_analyses)
        if total_regression_analyses > 0 else 0)
    ca_error_rate = (
        float(culprit_analysis_errors) / float(total_culprit_analyses)
        if total_culprit_analyses > 0 else 0)
    return {
        'regression_analysis': int(ra_error_rate * 100),
        'culprit_analysis': int(ca_error_rate * 100)
    }

  def _CalculateXOverY(self, x, y):
    """Calculate the growth rate."""
    change = int(100 * float(x - y) / float(x)) if x != 0 else -100
    if change >= 0:
      return '{}% increase'.format(change)
    else:
      change = abs(change)
      return '{}% decrease'.format(change)

  def __repr__(self):
    """Return the string representation of this report."""
    if self._display_change:
      return FlakeAnalyzerReport._TEMPLATE_STRING.format(
          week_start=self._week_start.strftime('%x'),
          week_end=(
              self._week_start + datetime.timedelta(days=7)).strftime('%x'),
          number_of_analyses=self._query_results[0]['number_of_analyses'],
          number_of_analyses_dx=self._CalculateXOverY(
              self._query_results[0]['number_of_analyses'],
              self._query_results[1]['number_of_analyses']),
          rr_error_rate=self._error_rates[0]['regression_analysis'],
          rr_error_rate_dx=self._CalculateXOverY(
              self._error_rates[0]['regression_analysis'],
              self._error_rates[1]['regression_analysis']),
          number_of_culprits=self._query_results[0]['number_of_culprits'],
          number_of_culprits_dx=self._CalculateXOverY(
              self._query_results[0]['number_of_culprits'],
              self._query_results[1]['number_of_culprits']),
          ca_error_rate=self._error_rates[0]['culprit_analysis'],
          ca_error_rate_dx=self._CalculateXOverY(
              self._error_rates[0]['culprit_analysis'],
              self._error_rates[1]['culprit_analysis']),
          number_of_autoactions_taken=self._query_results[0][
              'number_of_autoactions_taken'],
          number_of_autoactions_taken_dx=self._CalculateXOverY(
              self._query_results[0]['number_of_autoactions_taken'],
              self._query_results[1]['number_of_autoactions_taken']),
          number_of_bugs_filed=self._query_results[0]['number_of_bugs_filed'],
          number_of_bugs_filed_dx=self._CalculateXOverY(
              self._query_results[0]['number_of_bugs_filed'],
              self._query_results[1]['number_of_bugs_filed']),
          number_of_bugs_commented=self._query_results[0][
              'number_of_bugs_commented'],
          number_of_bugs_commented_dx=self._CalculateXOverY(
              self._query_results[0]['number_of_bugs_commented'],
              self._query_results[1]['number_of_bugs_commented']),
          number_of_cls_commented=self._query_results[0][
              'number_of_cls_commented'],
          number_of_cls_commented_dx=self._CalculateXOverY(
              self._query_results[0]['number_of_cls_commented'],
              self._query_results[1]['number_of_cls_commented']),
      )
    return FlakeAnalyzerReport._TEMPLATE_STRING_NO_CHANGE.format(
        week_start=self._week_start.strftime('%x'),
        week_end=(self._week_start + datetime.timedelta(days=7)).strftime('%x'),
        number_of_analyses=self._query_results[0]['number_of_analyses'],
        rr_error_rate=self._error_rates[0]['regression_analysis'],
        number_of_culprits=self._query_results[0]['number_of_culprits'],
        ca_error_rate=self._error_rates[0]['culprit_analysis'],
        number_of_autoactions_taken=self._query_results[0][
            'number_of_autoactions_taken'],
        number_of_bugs_filed=self._query_results[0]['number_of_bugs_filed'],
        number_of_bugs_commented=self._query_results[0][
            'number_of_bugs_commented'],
        number_of_cls_commented=self._query_results[0][
            'number_of_cls_commented'],
    )


if __name__ == '__main__':
  # Last 6 weeks of data.
  print FlakeAnalyzerReport(0)
  print '--------------------------------------------------------------------'
  print FlakeAnalyzerReport(7)
  print '--------------------------------------------------------------------'
  print FlakeAnalyzerReport(14)
  print '--------------------------------------------------------------------'
  print FlakeAnalyzerReport(21)
  print '--------------------------------------------------------------------'
  print FlakeAnalyzerReport(28)
  print '--------------------------------------------------------------------'
  print FlakeAnalyzerReport(35, display_change=False)
