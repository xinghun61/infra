# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_utils import pipelines
from pipeline_utils.appengine_third_party_pipeline_python_src_pipeline \
    import handlers as pipeline_handlers
from pipeline_utils.appengine_third_party_pipeline_python_src_pipeline \
    import pipeline as pipeline
from pipeline_utils.appengine_third_party_pipeline_python_src_pipeline \
    import status_ui as pipeline_status_ui


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
