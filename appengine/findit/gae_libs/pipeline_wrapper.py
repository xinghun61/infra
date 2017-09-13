# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Deprecated. Please use gae_libs/pipelines.py instead."""

import pipeline as pipeline
from pipeline import handlers as pipeline_handlers
from pipeline import status_ui as pipeline_status_ui


class BasePipeline(pipeline.Pipeline):  # pragma: no cover

  def send_result_email(self):
    """Overrides this function so that it doesn't send emails on completion."""
    pass

  def run_test(self, *args, **kwargs):
    pass

  def finalized_test(self, *args, **kwargs):
    pass

  def callback(self, **kwargs):
    pass

  def pipeline_status_path(self):
    """Returns an absolute path to look up the status of the pipeline."""
    return '/_ah/pipeline/status?root=%s&auto=false' % self.root_pipeline_id

  def run(self, *args, **kwargs):
    raise NotImplementedError()
