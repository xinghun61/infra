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
import re

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

from libs import time_util
from model.flake.flake_type import FlakeType

_TAG_DELIMITER = '::'
_REPORT_TIME_PATTERN = re.compile(r'\d+-W\d+-\d')


def GetReportDateString(report):
  """Gets the report time in a string to represent the data.

  Args:
    report (subclass of ReportRow).
  """
  report_time_iso_str = report.key.pairs()[0][1]
  assert _REPORT_TIME_PATTERN.match(report_time_iso_str), (
      'Cannot get date string if the time string is not for an ISO tuple.')
  return time_util.ConvertISOWeekStringToUTCDateString(report_time_iso_str)


class _TypeCount(ndb.Model):
  """Counts for a specific flake type."""
  flake_type = msgprop.EnumProperty(FlakeType, required=True)
  count = ndb.IntegerProperty(default=0)


class ReportRow(ndb.Model):
  """Base class for report elements."""
  # Aggregate counts for a subset of flake occurrences."""
  bug_count = ndb.IntegerProperty()
  impacted_cl_counts = ndb.StructuredProperty(_TypeCount, repeated=True)
  occurrence_counts = ndb.StructuredProperty(_TypeCount, repeated=True)
  test_count = ndb.IntegerProperty()

  generated_time = ndb.DateTimeProperty(auto_now_add=True)

  # Tags of a report row to ease queries.
  tags = ndb.StringProperty(repeated=True)

  @classmethod
  def FromTallies(cls, parent, d, year, week, day):
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
        bug_count=CountIfCollection(d.get('_bugs', 0)),
        impacted_cl_counts=[
            _TypeCount(flake_type=flake_type, count=CountIfCollection(cl_ids))
            for flake_type, cl_ids in d.get('_impacted_cls', {}).iteritems()
        ],
        occurrence_counts=[
            _TypeCount(flake_type=flake_type, count=count)
            for flake_type, count in d.get('_occurrences', {}).iteritems()
        ],
        test_count=CountIfCollection(d.get('_tests', 0)),
        tags=cls.GenerateTagList(d, year, week, day))

  @staticmethod
  def GenerateTag(tag_name, tag_value):
    return '{}{}{}'.format(tag_name, _TAG_DELIMITER, tag_value)

  @staticmethod
  def GenerateTagList(d, year, week, day):  # pylint: disable=unused-argument
    return [
        ReportRow.GenerateTag('year', year),
        ReportRow.GenerateTag('week', week),
        ReportRow.GenerateTag('day', day),
    ]

  @staticmethod
  def GetTagDelimiter():
    return _TAG_DELIMITER

  def GetTotalOccurrenceCount(self):
    return sum([
        occurrence_count.count
        for occurrence_count in self.occurrence_counts or []
    ])

  def GetTotalCLCount(self):
    return sum([cl_count.count for cl_count in self.impacted_cl_counts or []])

  def ToSerializable(self):
    impacted_cl_summary = {}
    for cl_count in self.impacted_cl_counts:
      impacted_cl_summary[cl_count.flake_type.name.lower()] = cl_count.count
    impacted_cl_summary['total'] = self.GetTotalCLCount()

    occurrence_summary = {}
    for occurrence_count in self.occurrence_counts:
      occurrence_summary[occurrence_count.flake_type.name
                         .lower()] = occurrence_count.count
    occurrence_summary['total'] = self.GetTotalOccurrenceCount()

    return {
        'id': self.key.id(),
        'bug_count': self.bug_count,
        'impacted_cl_counts': impacted_cl_summary,
        'occurrence_counts': occurrence_summary,
        'test_count': self.test_count,
    }


class TotalFlakinessReport(ReportRow):
  """A weekly report on flakiness occurrences"""
  # A report is identified by the ISO Week it covers.
  # This is meant to include all flake occurrences between Monday 00:00 PST and
  # the next Monday at the same time.

  @staticmethod
  def MakeId(year, week, day):
    # Compose a string like '2018-W02' to use as id for the report.
    return '%d-W%02d-%d' % (year, week, day)

  @classmethod
  def Get(cls, year, week, day):
    return ndb.Key(cls, cls.MakeId(year, week, day)).get()

  def GetReportTime(self):
    """Gets the start and end date of the time range of the report."""
    report_time_iso_str = self.key.pairs()[0][1]
    return time_util.ConvertISOWeekStringToUTCDateString(report_time_iso_str)


class ComponentFlakinessReport(ReportRow):
  """Entry for a given component"""

  @classmethod
  def Get(cls, report_key, component):
    key = ndb.Key(report_key.kind(), report_key.id(), cls, component)
    return key.get()

  @staticmethod
  def GenerateTagList(d, year, week, day):
    tags = super(ComponentFlakinessReport,
                 ComponentFlakinessReport).GenerateTagList(d, year, week, day)
    tags.append(ComponentFlakinessReport.GenerateTag('component', d['_id']))
    return tags

  @ndb.ComputedProperty
  def false_rejected_cl_count(self):
    for cl_count in self.impacted_cl_counts:
      if cl_count.flake_type == FlakeType.CQ_FALSE_REJECTION:
        return cl_count.count
    return 0

  def GetReportYearWeek(self):
    """Gets the year and week of the report.

    Key to a ComponentFlakinessReport:
      Key(TotalFlakinessReport, '{year}-W{week}-{day}',
          ComponentFlakinessReport, '{component}')
    """
    return self.key.pairs()[0][1][:-2]


class TestFlakinessReport(ReportRow):
  """Report entry for a given component/test combination"""

  @classmethod
  def Get(cls, component_report_key, test):
    key = ndb.Key(
        component_report_key.parent().kind(),
        component_report_key.parent().id(), component_report_key.kind(),
        component_report_key.id(), cls, test)
    return key.get()

  @staticmethod
  def GenerateTagList(d, year, week, day):
    tags = super(TestFlakinessReport, TestFlakinessReport).GenerateTagList(
        d, year, week, day)
    tags.append(TestFlakinessReport.GenerateTag('test', d['_id']))
    return tags
