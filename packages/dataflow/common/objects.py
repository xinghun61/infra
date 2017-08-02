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
    self.attempt_start_msec = None
    self.first_start_msec = None
    self.last_start_msec = None

    self.cq_name = None

  @staticmethod
  def get_bigquery_attributes():
    return [
        'attempt_start_msec',
        'first_start_msec',
        'last_start_msec',
        'cq_name',
    ]

  def update_first_start(self, new_timestamp):
    if new_timestamp is None:
      return
    if self.first_start_msec is None or new_timestamp < self.first_start_msec:
      self.first_start_msec = new_timestamp

  def update_last_start(self, new_timestamp):
    if new_timestamp is None:
      return
    if self.last_start_msec is None or new_timestamp > self.first_start_msec:
      self.last_start_msec = new_timestamp


class CQEvent(BigQueryObject):
  """A CQEvent represents event data reported to BigQuery from CQ.

     CQEvents are aggregated to make CQAttempts.
  """
  def __init__(self):
    self.timestamp_millis = None
    self.action = None
    self.attempt_start_usec = None
    self.cq_name = None

  @staticmethod
  def get_bigquery_attributes():
    return [
        'timestamp_millis',
        'action',
        'attempt_start_usec',
        'cq_name',
    ]
