# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from pipeline_utils import pipelines

from model.build import Build
from model.build_analysis_status import BuildAnalysisStatus


# TODO(stgao): remove BasePipeline after http://crrev.com/810193002 is landed.
class BasePipeline(pipelines.AppenginePipeline):  # pragma: no cover
  def run_test(self, *args, **kwargs):
    pass

  def finalized_test(self, *args, **kwargs):
    pass

  def callback(self, **kwargs):
    pass

  def run(self, *args, **kwargs):
    raise NotImplementedError()


class BuildFailurePipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number):
    build = Build.GetBuild(master_name, builder_name, build_number)

    # TODO: implement the logic.
    build.analysis_status = BuildAnalysisStatus.ANALYZED
    build.put()


@ndb.transactional
def NeedANewAnalysis(master_name, builder_name, build_number, force):
  """Check analysis status of a build and decide if a new analysis is needed.

  Returns:
    (build, need_analysis)
    build (Build): the build as specified by the input.
    need_analysis (bool): True if an analysis is needed, otherwise False.
  """
  build_key = Build.CreateKey(master_name, builder_name, build_number)
  build = build_key.get()

  if not build:
    build = Build.CreateBuild(master_name, builder_name, build_number)
    build.analysis_status = BuildAnalysisStatus.PENDING
    build.put()
    return build, True
  elif force:
    # TODO: avoid concurrent analysis.
    build.Reset()
    build.put()
    return build, True
  else:
    # TODO: support following cases
    # 1. Automatically retry if last analysis failed with errors.
    # 2. Start another analysis if the build cycle wasn't completed in last
    #    analysis request.
    # 3. Analysis is not complete and no update in the last 5 minutes.
    return build, False


def ScheduleAnalysisIfNeeded(master_name, builder_name, build_number, force,
                             queue_name):
  """Schedule an analysis if needed and return the build."""
  build, need_new_analysis = NeedANewAnalysis(
      master_name, builder_name, build_number, force)

  if need_new_analysis:
    pipeline_job = BuildFailurePipeline(master_name, builder_name, build_number)
    pipeline_job.start(queue_name=queue_name)

    logging.info('An analysis triggered on build %s, %s, %s: %s',
                 master_name, builder_name, build_number,
                 pipeline_job.pipeline_status_url())
  else:  # pragma: no cover
    logging.info('Analysis was already triggered or the result is recent.')

  return build
