# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from gae_libs import pipelines
from gae_libs.pipeline_wrapper import pipeline_handlers
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.notify_culprit_pipeline import (NotifyCulpritInput)
from pipelines.flake_failure.notify_culprit_pipeline import (
    NotifyCulpritPipeline)
from services.flake_failure import culprit_util
from waterfall.test.wf_testcase import WaterfallTestCase


class NotifyCulpritPipelineTest(WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(culprit_util, 'ShouldNotifyCulprit', return_value=False)
  def testNotifyCulpritPipelineShoudNotNotify(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    culprit = FlakeCulprit.Create('repo', 'r1000', 1000)
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()

    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    notify_culprit_input = NotifyCulpritInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    pipeline_job = NotifyCulpritPipeline(notify_culprit_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    pipeline_job = pipelines.pipeline.Pipeline.from_id(pipeline_job.pipeline_id)
    self.assertFalse(pipeline_job.outputs.default.value)

  @mock.patch.object(culprit_util, 'ShouldNotifyCulprit', return_value=True)
  @mock.patch.object(
      culprit_util, 'PrepareCulpritForSendingNotification', return_value=False)
  @mock.patch.object(culprit_util, 'NotifyCulprit')
  def testNotifyCulpritPipelineShoudNotifyAlreadyNotified(
      self, mocked_notify, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    culprit = FlakeCulprit.Create('repo', 'r1000', 1000)
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()

    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    notify_culprit_input = NotifyCulpritInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    pipeline_job = NotifyCulpritPipeline(notify_culprit_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertFalse(mocked_notify.called)

  @mock.patch.object(culprit_util, 'ShouldNotifyCulprit', return_value=True)
  @mock.patch.object(
      culprit_util, 'PrepareCulpritForSendingNotification', return_value=True)
  @mock.patch.object(culprit_util, 'NotifyCulprit')
  def testNotifyCulpritPipelineShoudNotify(self, mocked_notify, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    culprit = FlakeCulprit.Create('repo', 'r1000', 1000)
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()

    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.put()

    notify_culprit_input = NotifyCulpritInput(
        analysis_urlsafe_key=analysis.key.urlsafe())
    pipeline_job = NotifyCulpritPipeline(notify_culprit_input)
    pipeline_job.start()
    self.execute_queued_tasks()

    self.assertTrue(mocked_notify.called)
