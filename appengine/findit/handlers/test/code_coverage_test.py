# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from handlers import code_coverage
from libs.gitiles.gitiles_repository import GitilesRepository
from model.code_coverage import DependencyRepository
from model.code_coverage import PostsubmitReport
from waterfall.test.wf_testcase import WaterfallTestCase


class FetchSourceFileTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/coverage/task/fetch-source-file', code_coverage.FetchSourceFile),
      ('/coverage/task/process-data/.*', code_coverage.ProcessCodeCoverageData),
  ],
                                       debug=True)

  def testPermissionInProcessCodeCoverageData(self):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    response = self.test_app.post(
        '/coverage/task/process-data/123?format=json', status=401)
    self.assertEqual(('Either not log in yet or no permission. '
                      'Please log in with your @google.com account.'),
                     response.json_body.get('error_message'))

  @mock.patch.object(code_coverage, '_WriteFileContentToGs')
  @mock.patch.object(GitilesRepository, 'GetSource', return_value='test')
  @mock.patch.object(BaseHandler, 'IsRequestFromAppSelf', return_value=True)
  def testFetchSourceFile(self, mocked_is_request_from_appself,
                          mocked_gitiles_get_source, mocked_write_to_gs):
    root_repo_host = 'chromium.googlesource.com'
    root_repo_project = 'chromium/src'
    root_repo_revision = '111'
    path = '//v8/src/dir/file.cc'
    revision = '999'

    manifest = [
        DependencyRepository(
            path='//v8/',
            server_host='chromium.googlesource.com',
            project='v8/v8.git')
    ]
    report = PostsubmitReport(
        key=ndb.Key(
            PostsubmitReport, '%s$%s$%s' % (root_repo_host, root_repo_project,
                                            root_repo_revision)),
        server_host=root_repo_host,
        project=root_repo_project,
        revision=root_repo_revision,
        manifest=manifest)
    report.put()

    request_url = ('/coverage/task/fetch-source-file')
    params = {
        'report_key': report.key.urlsafe(),
        'path': path,
        'revision': revision
    }
    response = self.test_app.post(request_url, params=params)

    mocked_is_request_from_appself.assert_called()
    self.assertEqual(200, response.status_int)

    # Gitiles should fetch the revision of last_updated_revision instead of
    # root_repo_revision and the path should be relative to //v8/.
    mocked_gitiles_get_source.assert_called_with('src/dir/file.cc', '999')

    mocked_write_to_gs.assert_called_with(
        ('/source-files-for-coverage/chromium.googlesource.com/v8/v8.git/'
         'src/dir/file.cc/999'), 'test')
