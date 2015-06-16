# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This module is to provide Findit service APIs through Cloud Endpoints:

Current APIs include:
1. Analysis of build failures in Chromium waterfalls.
   Analyzes build failures and detects suspected CLs.
"""

import logging

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from waterfall import buildbot
from waterfall import build_failure_analysis_pipelines
from waterfall import masters


_BUILD_FAILURE_ANALYSIS_TASKQUEUE = 'build-failure-analysis-queue'


# This is used by the underlying ProtoRpc when creating names for the ProtoRPC
# messages below. This package name will show up as a prefix to the message
# class names in the discovery doc and client libraries.
package = 'FindIt'


# These subclasses of Message are basically definitions of Protocol RPC
# messages. https://cloud.google.com/appengine/docs/python/tools/protorpc/
class BuildFailure(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(3, variant=messages.Variant.INT32,
                                       required=True)
  failed_steps = messages.StringField(4, repeated=True, required=False)


class BuildFailureCollection(messages.Message):
  """Represents a request from a client, eg. builder_alerts."""
  builds = messages.MessageField(BuildFailure, 1, repeated=True)


class SuspectedCL(messages.Message):
  repo_name = messages.StringField(1, required=True)
  revision = messages.StringField(2, required=True)
  commit_position = messages.IntegerField(3, variant=messages.Variant.INT32)


class BuildFailureAnalysisResult(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(3, variant=messages.Variant.INT32,
                                       required=True)
  step_name = messages.StringField(4, required=True)
  is_sub_test = messages.BooleanField(5, variant=messages.Variant.BOOL,
                                      required=True)
  test_name = messages.StringField(6)
  first_known_failed_build_number=messages.IntegerField(
      7, variant=messages.Variant.INT32)
  suspected_cls = messages.MessageField(SuspectedCL, 8, repeated=True)


class BuildFailureAnalysisResultCollection(messages.Message):
  """Represents a response to the client, eg. builder_alerts."""
  results = messages.MessageField(BuildFailureAnalysisResult, 1, repeated=True)


# Create a Cloud Endpoints API.
# https://cloud.google.com/appengine/docs/python/endpoints/create_api
@endpoints.api(name='findit', version='v1', description='FindIt API')
class FindItApi(remote.Service):
  """FindIt API v1."""

  @endpoints.method(
      BuildFailureCollection, BuildFailureAnalysisResultCollection,
      path='buildfailure', name='buildfailure')
  def AnalyzeBuildFailures(self, request):
    """Returns analysis results for the given build failures in the request.

    Analysis of build failures will be triggered automatically on demand.

    Args:
      request (BuildFailureCollection): A list of build failures.

    Returns:
      BuildFailureAnalysisResultCollection
      A list of analysis results for the given build failures.
    """
    results = []

    logging.info('%d build failure(s).', len(request.builds))

    for build in request.builds:
      master_name = buildbot.GetMasterNameFromUrl(build.master_url)
      if not master_name:
        continue

      if not masters.MasterIsSupported(master_name):
        continue

      logging.info('Failed steps for build %s/%s/%d: %s',
                   master_name, build.builder_name, build.build_number,
                   ', '.join(build.failed_steps))

      force = False  #TODO: use the failed step to trigger incremental analysis.
      analysis = build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
          master_name, build.builder_name, build.build_number, force,
          _BUILD_FAILURE_ANALYSIS_TASKQUEUE)

      if not analysis.completed or analysis.failed:
        continue

      for failure in analysis.result['failures']:
        if not failure['suspected_cls']:
          continue

        suspected_cls = []
        for suspected_cl in failure['suspected_cls']:
          suspected_cls.append(SuspectedCL(
              repo_name=suspected_cl['repo_name'],
              revision=suspected_cl['revision'],
              commit_position=suspected_cl['commit_position']))

        results.append(BuildFailureAnalysisResult(
            master_url=build.master_url,
            builder_name=build.builder_name,
            build_number=build.build_number,
            step_name=failure['step_name'],
            is_sub_test=False,
            test_name=None,
            first_known_failed_build_number=failure['first_failure'],
            suspected_cls=suspected_cls))

    return BuildFailureAnalysisResultCollection(results=results)
