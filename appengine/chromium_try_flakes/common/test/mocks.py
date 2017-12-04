# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import datetime
import mock

from apiclient.errors import HttpError

# TODO(ehmaldonado): Consider using autospec to ensure that classes below clone
# the monorail API correctly.
class MockComment(object): # pragma: no cover
  def __init__(self, created, author, comment=None, labels=None, cc=None):
    self.created = created
    self.author = author
    self.comment = comment
    self.labels = labels or []
    self.cc = cc or []

class MockIssue(object): # pragma: no cover
  def __init__(self, issue_entry):
    self.id = issue_entry.get('id')
    self.project_id = issue_entry.get('project_id')
    self.created = issue_entry.get('created')
    self.summary = issue_entry.get('summary')
    self.description = issue_entry.get('description')
    self.status = issue_entry.get('status')
    self.labels = issue_entry.get('labels', [])
    self.components = issue_entry.get('components', [])
    self.owner = issue_entry.get('owner', {}).get('name')
    self.open = True
    self.closed = None
    self.updated = datetime.datetime.utcnow()
    self.comments = []
    self.cc = []
    self.merged_into = None
    self.merged_into_project = None

class MonorailDB(object): # pragma: no cover
  def __init__(self):
    self.issues = defaultdict(dict)
    self.next_issue_id = 100000

  def create(self, issue, project):
    issue.id = self.next_issue_id
    issue.project_id = project or self.project
    self.issues[project][issue.id] = issue
    self.next_issue_id += 1
    return issue

  def getComments(self, issue_id, project):
    return self.issues[project][issue_id].comments

  def postComment(self, issue_id, project, comment):
    self.issues[project][issue_id].comments.append(comment)

  def getIssue(self, issue_id, project):
    if project not in self.issues or issue_id not in self.issues[project]:
      raise HttpError(mock.Mock(status=404), '')
    return self.issues[project][issue_id]

  # pylint: disable=unused-argument
  def getIssues(self, query, project):
    return []

  def update(self, issue, comment):
    self.issues[issue.project_id][issue.id] = issue
    issue.comments.append(
        MockComment(datetime.datetime.utcnow(), 'app@ae.org', comment))

class MockIssueTrackerAPI(object): # pragma: no cover
  def __init__(self, database=None, project='chromium'):
    self.project = project
    self.database = database or MonorailDB()

  def create(self, issue):
    return self.database.create(issue, self.project)

  def getIssue(self, issue_id, project=None):
    project = project or self.project
    return self.database.getIssue(issue_id, project)

  # pylint: disable=unused-argument
  def getIssues(self, query, project=None):
    project = project or self.project
    return self.database.getIssues(query, project)

  def getComments(self, issue_id):
    return self.database.getComments(issue_id, self.project)

  def postComment(self, issue_id, comment):
    self.database.postComment(issue_id, self.project, comment)

  def update(self, issue, comment):
    self.database.update(issue, comment)

  @property
  def issues(self):
    return self.database.issues[self.project]
