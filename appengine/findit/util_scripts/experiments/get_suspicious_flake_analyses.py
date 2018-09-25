"""Find likely false-positive flake analyses

And creates experiment specs for such analyses. See trigger_tasks.py for more
information.
"""
import datetime
import json
import os
import sys
import time

_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(1, _FINDIT_DIR)

# Activate script for Findit production.
from local_libs import remote_api
remote_api.EnableFinditRemoteApi()

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from infra_api_clients.swarming import swarming_util
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model import result_status
from services import try_job as try_job_service
from waterfall import build_util

_HTTP_CLIENT = FinditHttpClient()

# How far to look back for analyses. 60 days is reasonable because isolate
# should keep data for around this long.
LOOK_BACK_DAYS = 60

# These pass rate thresholds are used to determine that an analysis is
# suspicious. i.e. The culprit is only barely flaky, which suggests that the
# preceding points may be just as flaky, but just happened to not fail when
# evaluated by Findit.
STABLE_PASS_RATE = .999
BARELY_FLAKY_PASS_RATE = .949


def GetRecentFlakeAnalysesWithCulprit():
  """Gets all untriaged flake analyses with a culprit in the given window."""
  window_start = datetime.datetime.now() - datetime.timedelta(
      days=LOOK_BACK_DAYS)
  return MasterFlakeAnalysis.query(
      MasterFlakeAnalysis.result_status == result_status.FOUND_UNTRIAGED,
      MasterFlakeAnalysis.request_time > window_start)


def GetSuspiciousFlakeAnalyses():
  """Gets flake analyses that are suspicious.

  Suspicious analyses are those that:
   - Have a culprit that has low flakiness.
   - Are not yet triaged.
  """

  query = GetRecentFlakeAnalysesWithCulprit()
  more = True
  cursor = None
  while more:
    analyses, cursor, more = query.fetch_page(100, start_cursor=cursor)
    for analysis in analyses:
      culprit_datapoint, previous_datapoint = GetCulpritAndPreviousDataPoints(
          analysis)
      if (previous_datapoint.pass_rate >= STABLE_PASS_RATE and
          culprit_datapoint.pass_rate >= BARELY_FLAKY_PASS_RATE):
        yield (analysis, previous_datapoint, culprit_datapoint)
  return


def GetCulpritAndPreviousDataPoints(analysis):
  """Gets the culprit datapoint and the one preceding it."""
  culprit_cp = ndb.Key(
      urlsafe=analysis.culprit_urlsafe_key).get().commit_position
  datapoints = sorted(analysis.data_points, key=lambda x: x.commit_position)
  for i in range(len(datapoints) - 1):
    if datapoints[i + 1].commit_position == culprit_cp:
      return datapoints[i + 1], datapoints[i]
  return None, None


def GenerateExperiments():
  """Iterate over suspicious analyses and create an experiment for each.

  This is meant to work with the experiment triggering and collecting scripts in
  https://chromium-review.googlesource.com/c/infra/infra/+/1180589
  """
  for analysis, stable_point, flaky_point in GetSuspiciousFlakeAnalyses():
    dimensions = try_job_service.GetTrybotDimensions(analysis.master_name,
                                                     analysis.builder_name)
    for i in range(len(dimensions)):
      if dimensions[i].startswith('pool:'):
        # Regardless what pool the task was originally triggered on, we better
        # trigger its experiment on the public Chrome pool.
        dimensions[i] = 'pool:Chrome'
        break
    stable_swarming_task_request = swarming_util.GetSwarmingTaskRequest(
        'chromium-swarm.appspot.com', stable_point.task_ids[0], _HTTP_CLIENT)
    args = stable_swarming_task_request.properties.extra_args.ToSerializable()
    flaky_swarming_task_request = swarming_util.GetSwarmingTaskRequest(
        'chromium-swarm.appspot.com', flaky_point.task_ids[0], _HTTP_CLIENT)

    # Replace the repeat count argument with a template.
    for i in range(len(args)):
      if args[i].startswith('--gtest_repeat='):
        args[i] = '--gtest_repeat=%d'
        break
    now_ts = time.time()
    now_milliseconds = now_ts * 1000
    # Get only the tail of the timestamp, exclude the part that doesn't change
    # during the whole day.
    ts_tail = int(now_milliseconds % 10e7)  # There's 8.64e7 ms in a day.
    experiment_id = time.strftime('experiment-%Y%m%d-') + str(ts_tail)
    yield {
        'experiment_id':
            experiment_id,
        'experiment_start':
            int(now_ts),
        'repeats_per_task':
            1,
        'task_count':
            430,
        'dimensions':
            ','.join(dimensions),
        'master_name':
            analysis.master_name,
        'builder_name':
            analysis.builder_name,
        'build_number':
            analysis.build_number,
        'bug':
            analysis.bug_id,
        'analysis_key':
            analysis.key.urlsafe(),
        'rows': [{
            'isolate_hash':
                stable_swarming_task_request.properties.inputs_ref.isolated,
            'expected_stable':
                True,
        }, {
            'isolate_hash':
                flaky_swarming_task_request.properties.inputs_ref.isolated,
            'expected_stable':
                False,
        }],
        'additional_args_template':
            ' '.join(args),
        'name':
            '%s-%d-%s' % (_Normalize(
                analysis.builder_name), analysis.build_number,
                          _Normalize(analysis.test_name)),
    }


def _Normalize(s, max_len=8):
  """Get the first few alphanum chars of a string"""
  result = ''
  for c in s:
    if ('a' <= c <= 'z' or 'A' <= c <= 'Z' or '0' <= c <= '9'):
      result += c
      if len(result) >= max_len:
        break
  return result


def main():
  output_path = sys.argv[1]
  for experiment in GenerateExperiments():
    file_name = 'experiment-%s.json' % experiment['name']
    if output_path:
      file_path = os.path.join(output_path, file_name)
    else:
      file_path = file_name
    if not os.path.isfile(file_path):
      json.dump(
          experiment, open(file_path, 'w'), indent=4, separators=(',', ': '))


if __name__ == '__main__':
  sys.exit(main())
