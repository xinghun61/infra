# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Issue object for working with issue tracker issues"""

import copy
import re
from monorail_api.change_tracking_list import ChangeTrackingList
from monorail_api.utils import parseDateTime

_LIST_FIELDS = ['blocked_on', 'blocking', 'labels', 'components', 'cc']

class Issue(object):
  def __init__(self, issue_entry):
    # Change these directly via __dict__ to avoid triggering __setattr_ below,
    # which would immediately mark issue dirty again.
    self.__dict__['_dirty'] = False
    self.__dict__['_changed'] = set()

    self.id = issue_entry.get('id')
    self.blocked_on = ChangeTrackingList(
        e['issueId'] for e in issue_entry.get('blockedOn', []))
    self.blocking = ChangeTrackingList(
        e['issueId'] for e in issue_entry.get('blocking', []))
    self.merged_into = issue_entry.get('mergedInto', {}).get('issueId')
    self.merged_into_project = (
        issue_entry.get('mergedInto', {}).get('projectId'))
    self.created = parseDateTime(issue_entry.get('published'))
    self.updated = parseDateTime(issue_entry.get('updated'))
    self.closed = parseDateTime(issue_entry.get('closed'))
    self.summary = issue_entry.get('summary')
    self.description = issue_entry.get('description')
    self.reporter = issue_entry.get('author', {}).get('name')
    self.owner = issue_entry.get('owner', {}).get('name')
    self.status = issue_entry.get('status')
    self.stars = issue_entry.get('stars')
    self.open = issue_entry.get('state') == 'open'
    self.labels = ChangeTrackingList(issue_entry.get('labels', []))
    self.components = ChangeTrackingList(issue_entry.get('components', []))
    self.cc = ChangeTrackingList([e['name'] for e in issue_entry.get('cc', [])])
    self.project_id = issue_entry.get('projectId')

    self.setClean()

  @property
  def dirty(self):
    return (self.__dict__['_dirty'] or
            any(self.__dict__[key].isChanged() for key in _LIST_FIELDS))

  @property
  def changed(self):
    res = self.__dict__['_changed']
    for key in _LIST_FIELDS:
      if self.__dict__[key].isChanged():
        res.add(key)
    return res

  def setClean(self):
    for key in _LIST_FIELDS:
      self.__dict__[key].reset()
    self.__dict__['_changed'].clear()
    self.__dict__['_dirty'] = False


  def __setattr__(self, name, value):
    self.__dict__[name] = value
    self.__dict__['_dirty'] = True
    self.__dict__['_changed'].add(name)
