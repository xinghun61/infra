# Copyright (C) 2010 Google Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import collections
import json
import logging
import re
import sys
import traceback

from appengine_module.test_results.model.testfile import TestFile

JSON_RESULTS_FILE = "results.json"
JSON_RESULTS_FILE_SMALL = "results-small.json"
JSON_RESULTS_PREFIX = "ADD_RESULTS("
JSON_RESULTS_SUFFIX = ");"

JSON_RESULTS_MIN_TIME = 3
JSON_RESULTS_HIERARCHICAL_VERSION = 4
JSON_RESULTS_MAX_BUILDS = 500
JSON_RESULTS_MAX_BUILDS_SMALL = 100

ACTUAL_KEY = "actual"
BUG_KEY = "bugs"
BUILD_NUMBERS_KEY = "buildNumbers"
BUILDER_NAME_KEY = "builder_name"
EXPECTED_KEY = "expected"
FAILURE_MAP_KEY = "failure_map"
FAILURES_BY_TYPE_KEY = "num_failures_by_type"
FIXABLE_COUNTS_KEY = "fixableCounts"
RESULTS_KEY = "results"
TESTS_KEY = "tests"
TIME_KEY = "time"
TIMES_KEY = "times"
VERSIONS_KEY = "version"

AUDIO = "A"
CRASH = "C"
FAIL = "Q"
# This is only output by gtests.
FLAKY = "L"
IMAGE = "I"
IMAGE_PLUS_TEXT = "Z"
MISSING = "O"
NO_DATA = "N"
NOTRUN = "Y"
PASS = "P"
SKIP = "X"
TEXT = "F"
TIMEOUT = "T"
LEAK = "K"

AUDIO_STRING = "AUDIO"
CRASH_STRING = "CRASH"
IMAGE_PLUS_TEXT_STRING = "IMAGE+TEXT"
IMAGE_STRING = "IMAGE"
FAIL_STRING = "FAIL"
FLAKY_STRING = "FLAKY"
MISSING_STRING = "MISSING"
NO_DATA_STRING = "NO DATA"
NOTRUN_STRING = "NOTRUN"
PASS_STRING = "PASS"
SKIP_STRING = "SKIP"
TEXT_STRING = "TEXT"
TIMEOUT_STRING = "TIMEOUT"
LEAK_STRING = "LEAK"

FAILURE_TO_CHAR = {
    AUDIO_STRING: AUDIO,
    CRASH_STRING: CRASH,
    IMAGE_PLUS_TEXT_STRING: IMAGE_PLUS_TEXT,
    IMAGE_STRING: IMAGE,
    FLAKY_STRING: FLAKY,
    FAIL_STRING: FAIL,
    MISSING_STRING: MISSING,
    NO_DATA_STRING: NO_DATA,
    NOTRUN_STRING: NOTRUN,
    PASS_STRING: PASS,
    SKIP_STRING: SKIP,
    TEXT_STRING: TEXT,
    TIMEOUT_STRING: TIMEOUT,
    LEAK_STRING: LEAK,
}

# FIXME: Use dict comprehensions once we update the server to python 2.7.
CHAR_TO_FAILURE = dict((value, key) for key, value in FAILURE_TO_CHAR.items())


def _is_directory(subtree):  # pragma: no cover
  return (RESULTS_KEY not in subtree
      or not isinstance(subtree[RESULTS_KEY], collections.Sequence))


class JsonResults(object):

  @staticmethod
  def is_aggregate_file(name):  # pragma: no cover
    return name in (JSON_RESULTS_FILE, JSON_RESULTS_FILE_SMALL)

  @classmethod
  def _strip_prefix_suffix(cls, data):  # pragma: no cover
    if (data.startswith(JSON_RESULTS_PREFIX)
        and data.endswith(JSON_RESULTS_SUFFIX)):
      return data[len(JSON_RESULTS_PREFIX):len(data) - len(JSON_RESULTS_SUFFIX)]
    return data

  @classmethod
  def _generate_file_data(cls, jsonObject, sort_keys=False):  # pragma: no cover
    return json.dumps(jsonObject, separators=(',', ':'), sort_keys=sort_keys)

  @classmethod
  def load_json(cls, file_data):  # pragma: no cover
    json_results_str = cls._strip_prefix_suffix(file_data)
    if not json_results_str:
      logging.warning("No json results data.")
      return None

    try:
      return json.loads(json_results_str)
    except: # FIXME: This should be specific! # pylint: disable=W0702
      logging.debug(json_results_str)
      logging.error("Failed to load json results: %s" %
         traceback.print_exception(*sys.exc_info()))
      return None

  @classmethod
  def _merge_json(cls, aggregated_json, incremental_json,
        num_runs):  # pragma: no cover
    # We have to delete expected entries because the incremental json may not
    # have any entry for every test in the aggregated json. But, the incremental
    # json will have all the correct expected entries for that run.
    cls._delete_expected_entries(aggregated_json[TESTS_KEY])
    cls._merge_non_test_data(aggregated_json, incremental_json, num_runs)
    incremental_tests = incremental_json[TESTS_KEY]
    if incremental_tests:
      aggregated_tests = aggregated_json[TESTS_KEY]
      cls._merge_tests(aggregated_tests, incremental_tests, num_runs)

  @classmethod
  def _delete_expected_entries(cls, aggregated_json):  # pragma: no cover
    for key in aggregated_json:
      item = aggregated_json[key]
      if _is_directory(item):
        cls._delete_expected_entries(item)
      else:
        if EXPECTED_KEY in item:
          del item[EXPECTED_KEY]
        if BUG_KEY in item:
          del item[BUG_KEY]

  @classmethod
  def _merge_non_test_data(cls, aggregated_json, incremental_json,
        num_runs):  # pragma: no cover
    incremental_builds = incremental_json[BUILD_NUMBERS_KEY]

    # FIXME: It's no longer possible to have multiple runs worth of data in the
    # incremental_json, so we can get rid of this for-loop and
    # the associated index.
    for index in reversed(range(len(incremental_builds))):
      build_number = int(incremental_builds[index])
      logging.debug(
          "Merging build %s, incremental json index: %d.", build_number, index)

      # Merge this build into aggreagated results.
      cls._merge_one_build(aggregated_json, incremental_json, index, num_runs)

  @classmethod
  def _merge_one_build(cls, aggregated_json, incremental_json,
        incremental_index, num_runs):  # pragma: no cover
    for key in incremental_json.keys():
      # Merge json results except "tests" properties (results, times etc).
      # "tests" properties will be handled separately.
      if key == TESTS_KEY or key == FAILURE_MAP_KEY:
        continue

      if key in aggregated_json:
        if key == FAILURES_BY_TYPE_KEY:
          cls._merge_one_build(aggregated_json[key], incremental_json[
                               key], incremental_index, num_runs=num_runs)
        else:
          aggregated_json[key].insert(
              0, incremental_json[key][incremental_index])
          aggregated_json[key] = aggregated_json[key][:num_runs]
      else:
        aggregated_json[key] = incremental_json[key]

  @classmethod
  def _merge_tests(cls, aggregated_json, incremental_json,
        num_runs):  # pragma: no cover
    # FIXME: Some data got corrupted and has results/times at the directory
    # level. Once the data is fixed, this should assert that the directory
    # level does not have
    # results or times and just return "RESULTS_KEY not in subtree".
    if RESULTS_KEY in aggregated_json:
      del aggregated_json[RESULTS_KEY]
    if TIMES_KEY in aggregated_json:
      del aggregated_json[TIMES_KEY]

    all_tests = set(aggregated_json.iterkeys())
    if incremental_json:
      all_tests |= set(incremental_json.iterkeys())

    for test_name in all_tests:
      if test_name not in aggregated_json:
        aggregated_json[test_name] = incremental_json[test_name]
        continue

      incremental_sub_result = None
      if incremental_json and test_name in incremental_json:
        incremental_sub_result = incremental_json[test_name]
      if _is_directory(aggregated_json[test_name]):
        cls._merge_tests(
            aggregated_json[test_name], incremental_sub_result, num_runs)
        continue

      aggregated_test = aggregated_json[test_name]

      if incremental_sub_result:
        results = incremental_sub_result[RESULTS_KEY]
        times = incremental_sub_result[TIMES_KEY]
        if (EXPECTED_KEY in incremental_sub_result
          and incremental_sub_result[EXPECTED_KEY] != PASS_STRING):
          aggregated_test[EXPECTED_KEY] = incremental_sub_result[EXPECTED_KEY]
        if BUG_KEY in incremental_sub_result:
          aggregated_test[BUG_KEY] = incremental_sub_result[BUG_KEY]
      else:
        results = [[1, NO_DATA]]
        times = [[1, 0]]

      cls._insert_item_run_length_encoded(
          results, aggregated_test[RESULTS_KEY], num_runs)
      cls._insert_item_run_length_encoded(
          times, aggregated_test[TIMES_KEY], num_runs)

  @classmethod
  def _insert_item_run_length_encoded(cls, incremental_items, aggregated_items,
      num_runs):  # pragma: no cover
    """Prepend incremental items to the aggregates list.

    Args:
      incremental_items: List to read of 2-item lists, [[count, value], ...]
      aggregated_items: List to modify of 2-item lists, [[count, value], ...]
      num_runs: Max number of runs for a single item.
    """
    for item in incremental_items:
      if len(aggregated_items) and item[1] == aggregated_items[0][1]:
        aggregated_items[0][0] = min(aggregated_items[0][0] + item[0], num_runs)
      else:
        aggregated_items.insert(0, item)

  @classmethod
  def _normalize_results(cls, aggregated_json, num_runs,
      run_time_pruning_threshold):  # pragma: no cover
    names_to_delete = []
    for test_name in aggregated_json:
      if _is_directory(aggregated_json[test_name]):
        cls._normalize_results(
            aggregated_json[test_name], num_runs, run_time_pruning_threshold)
        # If normalizing deletes all the children of this directory, also
        # delete the directory.
        if not aggregated_json[test_name]:
          names_to_delete.append(test_name)
      else:
        leaf = aggregated_json[test_name]
        leaf[RESULTS_KEY] = cls._remove_items_over_max_number_of_builds(
            leaf[RESULTS_KEY], num_runs)
        leaf[TIMES_KEY] = cls._remove_items_over_max_number_of_builds(
            leaf[TIMES_KEY], num_runs)
        if cls._should_delete_leaf(leaf, run_time_pruning_threshold):
          names_to_delete.append(test_name)

    for test_name in names_to_delete:
      del aggregated_json[test_name]

  @classmethod
  def _should_delete_leaf(cls, leaf,
        run_time_pruning_threshold):  # pragma: no cover
    if leaf.get(EXPECTED_KEY, PASS_STRING) != PASS_STRING:
      return False

    if BUG_KEY in leaf:
      return False

    deletable_types = set((PASS, NO_DATA, NOTRUN))
    for result in leaf[RESULTS_KEY]:
      if result[1] not in deletable_types:
        return False

    for time in leaf[TIMES_KEY]:
      if time[1] >= run_time_pruning_threshold:
        return False

    return True

  @classmethod
  def _remove_items_over_max_number_of_builds(cls, encoded_list,
        num_runs):  # pragma: no cover
    num_builds = 0
    index = 0
    for result in encoded_list:
      num_builds = num_builds + result[0]
      index = index + 1
      if num_builds >= num_runs:
        return encoded_list[:index]

    return encoded_list

  @classmethod
  def _convert_gtest_json_to_aggregate_results_format(cls,
        json_dict):  # pragma: no cover
    # FIXME: Change gtests over to uploading the full results format like
    # layout-tests so we don't have to do this normalizing.
    # http://crbug.com/247192.

    if FAILURES_BY_TYPE_KEY in json_dict:
      # This is already in the right format.
      return

    failures_by_type = {}
    for fixableCount in json_dict[FIXABLE_COUNTS_KEY]:
      for failure_type, count in fixableCount.items():
        failure_string = CHAR_TO_FAILURE[failure_type]
        if failure_string not in failures_by_type:
          failures_by_type[failure_string] = []
        failures_by_type[failure_string].append(count)
    json_dict[FAILURES_BY_TYPE_KEY] = failures_by_type

  @classmethod
  def _check_json(cls, builder, json_dict):  # pragma: no cover
    version = json_dict[VERSIONS_KEY]
    if version > JSON_RESULTS_HIERARCHICAL_VERSION:
      return "Results JSON version '%s' is not supported." % version

    if not builder in json_dict:
      return "Builder '%s' is not in json results." % builder

    results_for_builder = json_dict[builder]
    if not BUILD_NUMBERS_KEY in results_for_builder:
      return "Missing build number in json results."

    cls._convert_gtest_json_to_aggregate_results_format(json_dict[builder])

    # FIXME: Remove this once all the bots have cycled with this code.
    # The failure map was moved from the top-level to being below the builder
    # like everything else.
    if FAILURE_MAP_KEY in json_dict:
      del json_dict[FAILURE_MAP_KEY]

    # FIXME: Remove this code once the gtests switch over to uploading the
    # full_results.json format.
    # Once the bots have cycled with this code, we can move this loop into
    # _convert_gtest_json_to_aggregate_results_format.
    KEYS_TO_DELETE = ["fixableCount", "fixableCounts", "allFixableCount"]
    for key in KEYS_TO_DELETE:
      if key in json_dict[builder]:
        del json_dict[builder][key]

    return ""

  @classmethod
  def _populate_tests_from_full_results(cls, full_results,
        new_results):  # pragma: no cover
    if EXPECTED_KEY in full_results:
      expected = full_results[EXPECTED_KEY]
      if expected != PASS_STRING and expected != NOTRUN_STRING:
        new_results[EXPECTED_KEY] = expected
      time = int(
          round(full_results[TIME_KEY])) if TIME_KEY in full_results else 0
      new_results[TIMES_KEY] = [[1, time]]

      actual_failures = full_results[ACTUAL_KEY]
      encoded_failures = ""
      # Treat unexpected skips like NOTRUNs to avoid exploding the results JSON
      # files when a bot exits early (e.g. due to too many crashes/timeouts).
      if expected != SKIP_STRING and actual_failures == SKIP_STRING:
        expected = NOTRUN_STRING
        encoded_failures = FAILURE_TO_CHAR[NOTRUN_STRING]
      elif expected == NOTRUN_STRING:
        encoded_failures = FAILURE_TO_CHAR[NOTRUN_STRING]
      else:
        encoded_failures = "".join(
            FAILURE_TO_CHAR[f] for f in actual_failures.split(" "))
      new_results[RESULTS_KEY] = [[1, encoded_failures]]

      if BUG_KEY in full_results:
        new_results[BUG_KEY] = full_results[BUG_KEY]
      return

    for key in full_results:
      new_results[key] = {}
      cls._populate_tests_from_full_results(
          full_results[key], new_results[key])

  @classmethod
  def _convert_full_results_format_to_aggregate(cls,
        full_results_format):  # pragma: no cover
    failures_by_type = full_results_format[FAILURES_BY_TYPE_KEY]

    tests = {}
    cls._populate_tests_from_full_results(full_results_format[TESTS_KEY], tests)

    # FIXME: Use dict comprehensions once we update the server to
    # python 2.7.
    failures_by_type_key = dict((k, [v]) for k, v in failures_by_type.items())
    aggregate_results_format = {
        VERSIONS_KEY: JSON_RESULTS_HIERARCHICAL_VERSION,
        full_results_format[BUILDER_NAME_KEY]: {
            FAILURES_BY_TYPE_KEY: failures_by_type_key,
            TESTS_KEY: tests,
            # FIXME: Have all the consumers of this switch over to the
            # full_results_format keys so we don't have to do this silly
            # conversion. Or switch the full_results_format keys
            # to be camel-case.
            BUILD_NUMBERS_KEY: [full_results_format['build_number']],
            'chromeRevision': [full_results_format['chromium_revision']],
            'blinkRevision': [full_results_format['blink_revision']],
            'secondsSinceEpoch': [full_results_format['seconds_since_epoch']],
        }
    }
    return aggregate_results_format

  @classmethod
  def _get_incremental_json(cls, builder, results_json,
        is_full_results_format):  # pragma: no cover
    if not results_json:
      return "No incremental JSON data to merge.", 403

    if is_full_results_format:
      logging.info("Converting full results format to aggregate.")
      results_json = cls._convert_full_results_format_to_aggregate(
          results_json)

    logging.info("Checking incremental json.")
    check_json_error_string = cls._check_json(builder, results_json)
    if check_json_error_string:
      return check_json_error_string, 403
    return results_json, 200

  @classmethod
  def _get_aggregated_json(cls, builder, aggregated_string):  # pragma: no cover
    logging.info("Loading existing aggregated json.")
    aggregated_json = cls.load_json(aggregated_string)
    if not aggregated_json:
      return None, 200

    logging.info("Checking existing aggregated json.")
    check_json_error_string = cls._check_json(builder, aggregated_json)
    if check_json_error_string:
      return check_json_error_string, 500

    return aggregated_json, 200

  @classmethod
  def merge(cls, builder, aggregated_string, incremental_json, num_runs,
        sort_keys=False):  # pragma: no cover
    aggregated_json, status_code = cls._get_aggregated_json(
        builder, aggregated_string)
    if not aggregated_json:
      aggregated_json = incremental_json
    elif status_code != 200:
      return aggregated_json, status_code
    else:
      if (aggregated_json[builder][BUILD_NUMBERS_KEY][0]
            == incremental_json[builder][BUILD_NUMBERS_KEY][0]):
        status_string = ("Incremental JSON's build number %s is the latest "
                         "build number in the aggregated JSON.") % str(
            aggregated_json[builder][BUILD_NUMBERS_KEY][0])
        return status_string, 409

      logging.info("Merging json results.")
      try:
        cls._merge_json(aggregated_json[builder],
            incremental_json[builder], num_runs)
      except: # FIXME: This should be specific! # pylint: disable=W0702
        return ("Failed to merge json results: %s" %
            traceback.print_exception(*sys.exc_info()), 500)

    aggregated_json[VERSIONS_KEY] = JSON_RESULTS_HIERARCHICAL_VERSION
    aggregated_json[builder][FAILURE_MAP_KEY] = CHAR_TO_FAILURE

    is_debug_builder = re.search(r"(Debug|Dbg)", builder, re.I)
    run_time_pruning_threshold = 3 * \
        JSON_RESULTS_MIN_TIME if is_debug_builder else JSON_RESULTS_MIN_TIME
    cls._normalize_results(aggregated_json[builder][TESTS_KEY], num_runs,
        run_time_pruning_threshold)
    return cls._generate_file_data(aggregated_json, sort_keys), 200

  @classmethod
  def _get_aggregate_file(cls, master, builder, test_type, filename,
        deprecated_master):  # pragma: no cover
    files = TestFile.get_files(master, builder, test_type, None, filename)
    if files:
      return files[0]

    if deprecated_master:
      files = TestFile.get_files(
          deprecated_master, builder, test_type, None, filename)
      if files:
        deprecated_file = files[0]
        # Change the master so it gets saved out with the new master name.
        deprecated_file.master = master
        return deprecated_file

    record = TestFile()
    record.master = master
    record.builder = builder
    record.test_type = test_type
    record.build_number = None
    record.name = filename
    record.data = ""
    return record

  @classmethod
  def is_valid_full_results_json(cls, file_json):
    if not isinstance(file_json, dict):
      return False
    required_fields = ['chromium_revision', 'blink_revision',
                       'build_number', 'version', 'builder_name',
                       'seconds_since_epoch', 'num_failures_by_type',
                       'tests']
    for required_field in required_fields:
      if required_field not in file_json:
        return False

    def is_convertable_to_int(value):
      try:
        int(value)
        return True
      except ValueError:
        return False

    int_fields = ['blink_revision', 'build_number', 'version',
                  'seconds_since_epoch']
    for int_field in int_fields:
      if not is_convertable_to_int(file_json[int_field]):
        return False

    def is_git_hash(value):
      return (isinstance(value, basestring) and len(value) == 40 and
              all([ch.lower() in '0123456789abcdef' for ch in value]))

    if not is_git_hash(file_json['chromium_revision']):
      pass # some projects still return numeric chromium revision

    if (not isinstance(file_json['num_failures_by_type'], dict) or
        not isinstance(file_json['tests'], dict)):
      return False

    for failure_type, num in file_json['num_failures_by_type'].iteritems():
      if not isinstance(failure_type, basestring):
        return False
      if not is_convertable_to_int(num):
        return False

    def validate_tests_tree(node):
      leaf = 'actual' in node or 'expected' in node
      if leaf:
        if 'actual' not in node or 'expected' not in node:
          return False
        if (not isinstance(node['actual'], basestring) or
            not isinstance(node['expected'], basestring)):
          return False
        if 'time' in node and not is_convertable_to_int(node['time']):
          return False
      else:
        for key, child_node in node.iteritems():
          if not isinstance(key, basestring):
            return False
          if not isinstance(child_node, dict):
            return False
          if not validate_tests_tree(child_node):
            return False
      return True

    if not validate_tests_tree(file_json['tests']):
      return False

    return True

  @classmethod
  def update(cls, master, builder, test_type, results_json, deprecated_master,
        is_full_results_format):  # pragma: no cover
    logging.info("Updating %s and %s." %
                 (JSON_RESULTS_FILE_SMALL, JSON_RESULTS_FILE))
    if (is_full_results_format and
        not cls.is_valid_full_results_json(results_json)):
      return ('Invalid full_results.json file.', 500)
    small_file = cls._get_aggregate_file(
        master, builder, test_type, JSON_RESULTS_FILE_SMALL, deprecated_master)
    large_file = cls._get_aggregate_file(
        master, builder, test_type, JSON_RESULTS_FILE, deprecated_master)
    return cls.update_files(builder, results_json, small_file, large_file,
        is_full_results_format)

  @classmethod
  def update_files(cls, builder, results_json, small_file, large_file,
        is_full_results_format):  # pragma: no cover
    incremental_json, status_code = cls._get_incremental_json(
        builder, results_json, is_full_results_format)
    if status_code != 200:
      return incremental_json, status_code

    status_string, status_code = cls.update_file(
        builder, small_file, incremental_json, JSON_RESULTS_MAX_BUILDS_SMALL)
    if status_code != 200:
      return status_string, status_code

    return cls.update_file(builder, large_file, incremental_json,
        JSON_RESULTS_MAX_BUILDS)

  @classmethod
  def update_file(cls, builder, record, incremental_json,
        num_runs):  # pragma: no cover
    new_results, status_code = cls.merge(
        builder, record.data, incremental_json, num_runs)
    if status_code != 200:
      return new_results, status_code
    return TestFile.save_file(record, new_results)

  @classmethod
  def _delete_results_and_times(cls, tests):  # pragma: no cover
    for key in tests.keys():
      if key in (RESULTS_KEY, TIMES_KEY):
        del tests[key]
      else:
        cls._delete_results_and_times(tests[key])

  @classmethod
  def get_test_list(cls, builder, json_file_data):  # pragma: no cover
    logging.debug("Loading test results json...")
    json_dict = cls.load_json(json_file_data)
    if not json_dict:
      return None

    logging.debug("Checking test results json...")

    check_json_error_string = cls._check_json(builder, json_dict)
    if check_json_error_string:
      return None

    test_list_json = {}
    tests = json_dict[builder][TESTS_KEY]
    cls._delete_results_and_times(tests)
    test_list_json[builder] = {TESTS_KEY: tests}
    return cls._generate_file_data(test_list_json)
