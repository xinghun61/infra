# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import apache_beam as beam

from apache_beam.pipeline import PipelineOptions


class EventsPipeline(beam.Pipeline):
  """Pipeline that reads options from the command line."""
  def __init__(self):
    super(EventsPipeline, self).__init__(options=PipelineOptions())


class BQRead(beam.io.iobase.Read):
  """Read transform created from a BigQuerySource with convenient defaults."""

  def __init__(self, query, validate=True, coder=None, use_standard_sql=True,
               flatten_results=False):
    """
    Args:
      query: The query to be run. Should specify table in
        `project.dataset.table` form for standard SQL and
        [project:dataset.table] form is use_standard_sql is False.
      See beam.io.BigQuerySource for explanation of remaining arguments.
    """
    source = beam.io.BigQuerySource(query=query, validate=validate, coder=coder,
                                    flatten_results=flatten_results,
                                    use_standard_sql=use_standard_sql)
    super(BQRead, self).__init__(source)


class BQWrite(beam.io.Write):
  """Write transform created from a BigQuerySink with convenient defaults.

     beam.io.BigQuerySink will automatically add unique insert ids to rows,
     which BigQuery uses to prevent duplicate inserts.
  """
  def __init__(self, project, table, dataset='aggregated',
               write_disposition=beam.io.BigQueryDisposition.WRITE_TRUNCATE):
    sink = beam.io.BigQuerySink(table, dataset, project,
                                write_disposition=write_disposition)
    super(BQWrite, self).__init__(sink)
