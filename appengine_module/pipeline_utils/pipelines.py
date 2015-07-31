# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from google.appengine.api import app_identity

from appengine_third_party_pipeline_python_src_pipeline import pipeline


class AppenginePipeline(pipeline.Pipeline):
  def send_result_email(self):  # pragma: no cover
    """We override this so it doesn't email on completion."""
    pass

  def pipeline_status_url(self):  # pragma: no cover
    """Returns a URL to look up the status of the pipeline."""
    scheme = 'https'
    if os.environ['APPLICATION_ID'].startswith('dev'):
      scheme = 'http'
    return '%s://%s/_ah/pipeline/status?root=%s&auto=false' % (
        scheme,
        app_identity.get_default_version_hostname(),
        self.root_pipeline_id)
