"""Comment object for working with issue tracker comments."""


import re
from issue_tracker.change_tracking_list import ChangeTrackingList
from issue_tracker.utils import parseDateTime


class Comment(object):  # pragma: no cover
  def __init__(self, comment_entry):
    self.author = comment_entry['author']['name']
    self.comment = comment_entry['content']
    self.created = parseDateTime(comment_entry['published'])
    self.id = comment_entry['id']

    if 'updates' in comment_entry and comment_entry['updates']:
      self.cc = ChangeTrackingList(
          [e for e in comment_entry['updates'].get('cc', [])])
      self.labels = ChangeTrackingList(
          [e for e in comment_entry['updates'].get('labels', [])])
      self.owner = comment_entry['updates'].get('owner', None)
      self.status = comment_entry['updates'].get('status', None)
      self.summary = comment_entry['updates'].get('summary', None)

      self.merged_into = [
          e for e in comment_entry['updates'].get('mergedInto', [])]
      self.blocked_on = [
          e for e in comment_entry['updates'].get('blockedOn', [])]
    else:
      self.cc = None
      self.labels = []
      self.owner = None
      self.status = None
      self.summary = None
      self.merged_into = []
      self.blocked_on = []

  def hasLabelContaining(self, regex):
    for label in self.labels:
      if re.search(regex, label, re.DOTALL | re.IGNORECASE):
        return True
    return False

  def getLabelsContaining(self, regex):
    rtn = []
    for label in self.labels:
      if re.search(regex, label, re.DOTALL | re.IGNORECASE):
        rtn.append(label)
    return rtn

  def hasLabelMatching(self, regex):
    return self.hasLabelContaining(regex + '\Z')

  def hasLabel(self, value):
    for label in self.labels:
      if label.lower() == value.lower():
        return True
    return False
