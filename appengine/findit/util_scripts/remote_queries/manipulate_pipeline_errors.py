# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""" This file is used to fix old analyses and categorize pipeline errors."""
import argparse
import collections
import datetime
import json
import os
import re
import sys

# Append path of Findit root directory to import remote_api.
_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(0, _FINDIT_DIR)

# Activate script as findit prod and set up sys.path properly.
from local_libs import remote_api
remote_api.EnableFinditRemoteApi()

# Add GAE and Findit imports below.
from google.appengine.ext import db
from google.appengine.ext import ndb

from libs import analysis_status
from libs import time_util
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipeline.models import _PipelineRecord
from pipeline import pipeline

_FLAKE_URL_TEMPLATE = ('https://analysis.chromium.org'
                       '/p/chromium/flake-portal/analysis/analyze?key=%s')


def _IterateOverIncompleteAnalyses(ndb_model_class, start_date, end_date,
                                   page_size):
  """Iterates over the incomplete analysis of the given model."""
  cursor = None
  more = True
  while more:
    query = ndb_model_class.query(ndb_model_class.request_time >= start_date,
                                  ndb_model_class.request_time < end_date)
    analyses, cursor, more = query.fetch_page(page_size, start_cursor=cursor)
    for analysis in analyses:
      if not analysis.completed:
        yield analysis


def SetIncompleteFlakeAnalysesToError(start_date, end_date, page_size):
  """Sets the incomplete flake analyses in the given time range to error."""
  if (datetime.datetime.utcnow() - end_date).total_seconds < 60 * 60 * 48:
    raise Exception('End date should be at least 48 hours before now: %r' %
                    datetime.datetime.utcnow())

  error = {
      'title': 'unknown',
      'description': 'unknown',
      'message': 'unknown',
  }
  count = 0
  for analysis in _IterateOverIncompleteAnalyses(
      MasterFlakeAnalysis, start_date, end_date, page_size):
    count += 1
    print count, ':', _FLAKE_URL_TEMPLATE % analysis.key.urlsafe()
    if not analysis.root_pipeline_id:
      analysis.Update(
          status=analysis_status.ERROR,
          error=error,
          start_time=(analysis.start_time or analysis.request_time) +
          datetime.timedelta(0, 1, 0),
          end_time=(analysis.updated_time or analysis.start_time or
                    analysis.request_time) + datetime.timedelta(0, 2, 0),
      )
    else:
      pipeline_key = db.Key.from_path(_PipelineRecord.kind(),
                                      analysis.root_pipeline_id)
      pr = db.get(pipeline_key)
      analysis.Update(
          status=analysis_status.ERROR,
          error=error,
          start_time=analysis.start_time or pr.start_time,
          end_time=analysis.end_time or pr.finalized_time or
          (pr.start_time + datetime.timedelta(0, 1, 0)),
      )


def DeleteSpammingFlakeAnalysis(start_date, end_date, page_size):
  """Deletes the spamming flake analysis. Please update code accordingly."""
  cursor = None
  more = True
  count = 0
  keys_to_delete = []
  while more:
    query = MasterFlakeAnalysis.query(
        MasterFlakeAnalysis.builder_name == 'Win10 Tests x64 (dbg)')
    analyses, cursor, more = query.fetch_page(page_size, start_cursor=cursor)
    for analysis in analyses:
      if (analysis.request_time < start_date or
          analysis.request_time >= end_date):
        print 'Not within time range:%r' % analysis.request_time
        continue
      if not analysis.failed:
        print 'Not failed'
        continue
      if not analysis.data_points:
        count += 1
        print count, ':', _FLAKE_URL_TEMPLATE % analysis.key.urlsafe()
        keys_to_delete.append(analysis.key)
      else:
        print 'There is some data point: %s' % (
            _FLAKE_URL_TEMPLATE % analysis.key.urlsafe())

  print 'Deleing %d flake analyses...' % len(keys_to_delete)
  ndb.delete_multi(keys_to_delete)


def BucketAbortedPipelines(start_date, end_date, page_size):
  """Buckets aborted pipelines according to the retry messages."""
  cursor = None
  more = True
  count = 0
  error_buckets = collections.defaultdict(
      lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
  pipeline_buckets = collections.defaultdict(int)
  message_pattern = re.compile(r'^([^: ]+): ([^: ]+):\d+ ([^ ]+) \$\$ (.*)$')
  while more:
    query = _PipelineRecord.all().filter('start_time >=', start_date).filter(
        'start_time <', end_date)
    if cursor:
      query.with_cursor(start_cursor=cursor)
    try:
      # _PipelineRecord inherits from db.Model instead of ndb.Model, so we can't
      # use fetch_page like we usually do in ndb.
      pipeline_records = query.fetch(page_size)
    except Exception as e:
      print e
      print '---------------- Partial result ------------------'
      break
    cursor = query.cursor()
    more = bool(len(pipeline_records) == page_size)
    print 'Checking %d pipelines' % len(pipeline_records)
    for p in pipeline_records:
      if p.status == _PipelineRecord.ABORTED and p.current_attempt > 0:
        count += 1
        print count, ':', p.retry_message

        # bucket by retry message
        match = message_pattern.match(p.retry_message)
        if match:
          exception_name, file_name, function_name, message = match.groups()
          bucket_name = '%s: %s %s' % (exception_name, file_name, function_name)
        else:
          bucket_name = p.retry_message
          message = p.retry_message

        # Extract info of the root pipeline.
        root_pipeline = p.root_pipeline
        arg_list, kwarg_dict = pipeline._dereference_args(
            root_pipeline.class_path, root_pipeline.params['args'],
            root_pipeline.params['kwargs'])
        if (root_pipeline.class_path.endswith('AnalyzeCompileFailurePipeline')
            or root_pipeline.class_path.endswith('AnalyzeTestFailurePipeline')):
          info = {
              'type': 'waterfall',
              'master': arg_list[0],
              'builder': arg_list[1],
              'build': arg_list[2],
          }
        elif root_pipeline.class_path.endswith('AnalyzeFlakePipeline'):
          info = {
              'type': 'flake',
              'key': kwarg_dict['analysis_urlsafe_key'],
          }
        else:
          print 'New analysis root pipeline: %s' % root_pipeline.class_path
          info = {}
        info['pipeline'] = p.root_pipeline.key().name()

        pipeline_buckets[p.class_path] += 1
        error_buckets[p.class_path][bucket_name][message].append(info)

  file_path = '/tmp/pipelines.js'
  with open(file_path, 'wb') as f:
    f.write('var pipelines = ')
    json.dump(error_buckets, f)
    f.write(';\n')
    f.write('var orderedKeys = ')
    json.dump(
        sorted(
            pipeline_buckets.keys(),
            key=lambda x: pipeline_buckets[x],
            reverse=True), f)
    f.write(';\n')

  print '*' * 80
  print 'Data is dumped to %s' % file_path


if __name__ == '__main__':
  description = """
  By default, only generate a data report of aborted pipelines by root cause.
  To manipulate the data in ndb, please carefully update the code accordingly.
  """
  parser = argparse.ArgumentParser(description=description)
  parser.add_argument(
      '-s',
      '--start_date',
      required=True,
      type=time_util.DatetimeFromString,
      help='A date in format YYYY-mm-dd, at or after which data are included.')
  parser.add_argument(
      '-e',
      '--end_date',
      required=True,
      type=time_util.DatetimeFromString,
      help='A date in format YYYY-mm-dd, before which data are included.')
  parser.add_argument(
      '-p',
      '--page_size',
      type=int,
      default=1000,
      help='An integer, number of entries to pull from datastore at a time.')
  options = parser.parse_args(sys.argv[1:])

  #SetIncompleteFlakeAnalysesToError(options.start_date, options.end_date,
  #                                  options.page_size)
  #DeleteSpammingFlakeAnalysis(options.start_date, options.end_date,
  #                            options.page_size)
  BucketAbortedPipelines(options.start_date, options.end_date,
                         options.page_size)
