# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import gae_ts_mon

from gae_libs import appengine_util

from handlers import code_coverage

# "code-coverage-backend" module.
code_coverage_backend_handler_mappings = [
    ('.*/coverage/task/fetch-source-file', code_coverage.FetchSourceFile),
    ('.*/coverage/task/process-data/.*', code_coverage.ProcessCodeCoverageData),
]
code_coverage_backend_web_application = webapp2.WSGIApplication(
    code_coverage_backend_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(code_coverage_backend_web_application)

# "code-coverage-frontend" module.
code_coverage_frontend_handler_mappings = [
    # TODO(crbug.com/924573): Migrate to '.*/coverage/api/coverage-data'.
    ('/coverage/api/coverage-data', code_coverage.ServeCodeCoverageData),
    # These mappings are separated so that ts_mon data (e.g. latency) is
    # groupable by view. (instead of a single entry like .*/coverage.*)
    ('.*/coverage', code_coverage.ServeCodeCoverageData),
    ('.*/coverage/component', code_coverage.ServeCodeCoverageData),
    ('.*/coverage/dir', code_coverage.ServeCodeCoverageData),
    ('.*/coverage/file', code_coverage.ServeCodeCoverageData),
]
code_coverage_frontend_web_application = webapp2.WSGIApplication(
    code_coverage_frontend_handler_mappings, debug=False)
if appengine_util.IsInProductionApp():
  gae_ts_mon.initialize(code_coverage_frontend_web_application)
