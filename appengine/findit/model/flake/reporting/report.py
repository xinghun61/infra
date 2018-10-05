# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Models to store weekly flakiness reports by component and test

These models are intended to hold aggregation of cq false rejection flake
occurrences taking place in a given week.

The TotalFlakinessReport will contain the number of occurrences, distinct
affected tests and distinct affected cls.

This data will be further broken down by component. ComponentFlakinessReport
will contain the same information for the subset of flake occurrences that are
related to a given component. (From the occurrence's Flake parent's component
field). These entities will be children entities of the TotalFlakinessReport
above.

The next level of aggregation is test name. TestFlakinessReport will contain
the same information as the above minus the 'distinct affected tests' as this
is obviated to 1. These will be children of the above and identified by the
normalized test name.
"""
import collections

from google.appengine.ext import ndb


class ReportRow(ndb.Model):
  """Base class for report elements."""
  # Aggregate counts for a subset of flake occurrences."""
  cq_false_rejection_occurrence_count = ndb.IntegerProperty()
  test_count = ndb.IntegerProperty()
  cl_count = ndb.IntegerProperty()

  @classmethod
  def FromTallies(cls, parent, d):
    """Create a report element from sets of values in a dict.

    The values in the tally may be counts, which will be used directly; or sets,
    whose cardinality will be used instead.
    """

    def CountIfCollection(x):
      if isinstance(x, collections.Sized):
        return len(x)
      return x

    return cls(
        parent=parent,
        id=d['_id'],
        cq_false_rejection_occurrence_count=CountIfCollection(
            d.get('_cq_false_rejection_occurrences', 0)),
        test_count=CountIfCollection(d.get('_tests', 0)),
        cl_count=CountIfCollection(d.get('_cls', 0)),
    )


class TotalFlakinessReport(ReportRow):
  """A weekly report on flakiness occurrences"""
  # A report is identified by the ISO Week it covers.
  # This is meant to include all flake occurrences between Monday 00:00 PST and
  # the next Monday at the same time.

  @staticmethod
  def MakeId(year, week_number):
    # Compose a string like '2018-W02' to use as id for the report.
    return '%d-W%02d' % (year, week_number)

  @classmethod
  def Get(cls, year, week_number):
    return ndb.Key(cls, cls.MakeId(year, week_number)).get()


class ComponentFlakinessReport(ReportRow):
  """Entry for a given component"""

  @classmethod
  def Get(cls, report_key, component):
    key = ndb.Key(report_key.kind(), report_key.id(), cls, component)
    return key.get()


class TestFlakinessReport(ReportRow):
  """Report entry for a given component/test combination"""

  @classmethod
  def Get(cls, component_report_key, test):
    key = ndb.Key(
        component_report_key.parent().kind(),
        component_report_key.parent().id(), component_report_key.kind(),
        component_report_key.id(), cls, test)
    return key.get()
