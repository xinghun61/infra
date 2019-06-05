# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd
""" Tasks and handlers for maintaining the spam classifier model. These
    should be run via cron and task queue rather than manually.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import cgi
import csv
import logging
import webapp2
import cloudstorage
import json

from datetime import date
from datetime import datetime
from datetime import timedelta

from framework import servlet
from framework import urls
from google.appengine.api import taskqueue
from google.appengine.api import app_identity
from framework import gcs_helpers

class TrainingDataExport(webapp2.RequestHandler):
  """Trigger a training data export task"""
  def get(self):
    logging.info("Training data export requested.")
    taskqueue.add(url=urls.SPAM_DATA_EXPORT_TASK + '.do')

BATCH_SIZE = 1000

class TrainingDataExportTask(servlet.Servlet):
  """Export any human-labeled ham or spam from the previous day. These
     records will be used by a subsequent task to create an updated model.
  """
  CHECK_SECURITY_TOKEN = False

  def ProcessFormData(self, mr, post_data):
    logging.info("Training data export initiated.")

    bucket_name = app_identity.get_default_gcs_bucket_name()
    date_str = date.today().isoformat()
    export_target_path = '/' + bucket_name + '/spam_training_data/' + date_str
    total_issues = 0

    with cloudstorage.open(export_target_path, mode='w',
        content_type=None, options=None, retry_params=None) as gcs_file:

      csv_writer = csv.writer(gcs_file, delimiter=',', quotechar='"',
          quoting=csv.QUOTE_ALL, lineterminator='\n')

      since = datetime.now() - timedelta(days=7)

      # TODO: Further pagination.
      issues, first_comments, _count = (
          self.services.spam.GetTrainingIssues(
              mr.cnxn, self.services.issue, since, offset=0, limit=BATCH_SIZE))
      total_issues += len(issues)
      for issue in issues:
        # Cloud Prediction API doesn't allow newlines in the training data.
        fixed_summary = issue.summary.replace('\r\n', ' ')
        fixed_comment = first_comments[issue.issue_id].replace('\r\n', ' ')
        email = self.services.user.LookupUserEmail(mr.cnxn, issue.reporter_id)
        csv_writer.writerow([
            'spam' if issue.is_spam else 'ham',
            fixed_summary.encode('utf-8'), fixed_comment.encode('utf-8'), email,
        ])

      comments = (
          self.services.spam.GetTrainingComments(
              mr.cnxn, self.services.issue, since, offset=0, limit=BATCH_SIZE))
      total_comments = len(comments)
      for comment in comments:
        # Cloud Prediction API doesn't allow newlines in the training data.
        fixed_comment = comment.content.replace('\r\n', ' ')
        email = self.services.user.LookupUserEmail(mr.cnxn, comment.user_id)
        csv_writer.writerow([
            'spam' if comment.is_spam else 'ham',
            # Comments don't have summaries, so it's blank:
            '', fixed_comment.encode('utf-8'), email
        ])

    self.response.body = json.dumps({
        "exported_issue_count": total_issues,
        "exported_comment_count": total_comments,
    })

