# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class BigQueryObject(object):
  """A BigQueryObject holds data that will be read from/written to BigQuery."""

  def __eq__(self, other):
    return self.__dict__ == other.__dict__

  @staticmethod
  def get_bigquery_attributes():
    """Returns a list of attributes that exist in the BigQuery schema.

       These attributes should be strings.
    """
    raise NotImplementedError()

  def as_bigquery_row(self):
    """Returns data in a suitable format for writing to BigQuery.

       The default behavior constructs a dictionary from the attributes listed
       by get_bigquery_attributes and their values. This behavior can be
       overridden.
    """
    return {attr: self.__dict__.get(attr)
            for attr in self.get_bigquery_attributes()}

  @classmethod
  def from_bigquery_row(cls, row):
    """Creates an instance of cls from a BigQuery row.

       Args:
         row: dictionary in the form {field: value} where field is in
         get_bigquery_attributes().
    """
    obj = cls()
    for field, value in row.items():
      obj.__dict__[field] = value
    return obj


class CQAttempt(BigQueryObject):
  """A CQAttempt represents a single CQ attempt.

     It is created by aggregating all CQEvents for a given attempt.
  """
  def __init__(self):
    # Consistent between events for a given attempt
    self.attempt_start_msec = None
    self.cq_name = None
    self.issue = None
    self.patchset = None
    self.dry_run = False

    # Patch event timestamps
    self.first_start_msec = None
    self.last_start_msec = None
    self.first_stop_msec = None
    self.last_stop_msec = None
    self.patch_committed_msec = None
    self.patch_started_to_commit_msec = None
    self.patch_failed_msec = None

    # Patch event bools
    self.committed = False
    self.was_throttled = False
    self.waited_for_tree = False
    self.failed = False

    # Verifier event timestamps
    self.first_verifier_trigger_msec = None
    self.patch_verifier_pass_msec = None
    self.cq_launch_latency_sec = None
    self.verifier_pass_latency_sec = None
    self.tree_check_and_throttle_latency_sec = None

    # Verifier event bools
    self.no_tryjobs_launched = False
    self.custom_trybots = False

    self.failure_reason = None
    self.max_failure_msec = None
    self.fail_type = None

    self.infra_failures = 0
    self.compile_failures = 0
    self.test_failures = 0
    self.invalid_test_results_failures = 0
    self.patch_failures = 0
    self.total_failures = 0

    self.max_bbucket_ids_msec = None
    self.contributing_bbucket_ids = None

  @staticmethod
  def get_bigquery_attributes():
    return [
        'attempt_start_msec',
        'first_start_msec',
        'last_start_msec',
        'cq_name',
        'first_stop_msec',
        'last_stop_msec',
        'committed',
        'was_throttled',
        'waited_for_tree',
        'issue',
        'patchset',
        'dry_run',
        'cq_launch_latency_sec',
        'verifier_pass_latency_sec',
        'tree_check_and_throttle_latency_sec',
        'no_tryjobs_launched',
        'custom_trybots',
        'failed',
        'infra_failures',
        'compile_failures',
        'test_failures',
        'invalid_test_results_failures',
        'patch_failures',
        'total_failures',
        'fail_type',
        'contributing_bbucket_ids',
    ]


class CQEvent(BigQueryObject):
  """A CQEvent represents event data reported to BigQuery from CQ.

     CQEvents are aggregated to make CQAttempts.
  """
  def __init__(self):
    self.timestamp_millis = None
    self.action = None
    self.attempt_start_usec = None
    self.cq_name = None
    self.issue = None
    self.patchset = None
    self.failure_reason = None
    self.dry_run = False
    self.contributing_buildbucket_ids = None

  @staticmethod
  def get_bigquery_attributes():
    return [
        'timestamp_millis',
        'action',
        'attempt_start_usec',
        'cq_name',
        'issue',
        'patchset',
        'dry_run',
        'failure_reason',
        'contributing_buildbucket_ids',
    ]
