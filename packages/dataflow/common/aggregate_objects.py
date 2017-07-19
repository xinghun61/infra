# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class BigQueryObject(object):
  """A BigQueryObject holds data that will be read from/written to BigQuery."""

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


class CQAttempt(BigQueryObject):
  """A CQAttempt represents a single CQ attempt.

     It is created by aggregating all CQ events for a given attempt.
  """
  def __init__(self):
    self.attempt_start_msec = None
    self.first_start_msec = None
    self.last_start_msec = None

  @staticmethod
  def get_bigquery_attributes():
    return [
        'attempt_start_msec',
        'first_start_msec',
        'last_start_msec',
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
