# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from gae_libs.handlers.base_handler import BaseHandler, Permission

from findit_v2.services import api


class BuildCompletionProcessor(BaseHandler):
  """Relays the completed build info to the service layer."""
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandlePost(self):
    # The data of self.request.body is from
    # findit/handlers/completed_build_pubsub_ingestor.py, and its format is:
    # {
    #   "project": "chromuim",
    #   "bucket": "ci",
    #   "builder_name": "Linux Builder",
    #   "build_id": 123243434,
    #   "build_result": "FAILURE",
    # }
    try:
      build = json.loads(self.request.body)
    except ValueError:
      logging.debug(self.request.body)
      raise

    project = build['project']
    bucket = build['bucket'].split('.')[-1]  # "luci.chromium.ci" => "ci"
    builder_name = build['builder_name']
    build_id = build['build_id']
    build_result = build['build_result']

    api.OnBuildCompletion(project, bucket, builder_name, build_id, build_result)
