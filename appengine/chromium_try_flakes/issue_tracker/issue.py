"""Issue object for working with issue tracker issues"""

import copy
import re
from issue_tracker.change_tracking_list import ChangeTrackingList
from issue_tracker.utils import parseDateTime

class Issue(object):
  def __init__(self, issue_entry):
    self.id = issue_entry['id']

    self.blocked_on = [e['issueId'] for e in issue_entry.get('blockedOn', [])]
    self.blocking =  [e['issueId'] for e in issue_entry.get('blocking', [])]

    self.merged_into = issue_entry.get('mergedInto', {}).get('issueId')

    self.created = parseDateTime(issue_entry['published'])
    self.updated = parseDateTime(issue_entry['updated'])

    if issue_entry.get('closed', []):
      self.closed = parseDateTime(issue_entry.get('closed', []))
    else:
      self.closed = None

    self.summary = issue_entry['summary']
    self.reporter = issue_entry.get('author', {}).get('name')
    self.owner = issue_entry.get('owner', {}).get('name')
    self.status = issue_entry.get('status')
    self.stars = issue_entry['stars']
    self.open = issue_entry['state'] == 'open'
    self.labels = ChangeTrackingList(issue_entry.get('labels', []))
    self.cc = ChangeTrackingList([e['name'] for e in issue_entry.get('cc', [])])

    self.dirty = False
    self.new = False
    self.changed = set()

  def __getattribute__(self, item):
    return object.__getattribute__(self, item)

  def __setattr__(self, name, value):
    self.__dict__[name] = value
    self.changed.add(name)
    self.dirty = True

    # If dirty flag was reset to false.
    if name == 'dirty' and not value:
      self.labels.reset()
      self.cc.reset()
      self.changed.clear()

  def addLabel(self, label):
    if not self.hasLabel(label):
      self.labels.append(label)
      self.dirty = True

  def __remove_label(self, label):
    for l in self.labels:
      if l.lower() == label.lower():
        self.labels.remove(l)
        self.dirty = True
        return

  def removeLabel(self, label):
    if self.hasLabel(label):
      self.__remove_label(label)
      self.addLabel('-%s' % label)

  def removeLabelByPrefix(self, prefix):
    labels = self.getLabelsByPrefix(prefix)
    for label in labels:
      self.removeLabel(label)

  def addCc(self, cc):
    if not self.hasCc(cc):
      self.cc.append(cc)
      self.dirty = True

  def removeCc(self, cc):
    if self.hasCc(cc):
      self.cc.remove(cc)
      self.dirty = True

  def getLabelsByPrefix(self, prefix):
    return self.getLabelsContaining('%s.*' % prefix)

  def getLabelByPrefix(self, prefix):
    rtn = self.getLabelsByPrefix(prefix)
    if rtn:
      return rtn[0]
    return None

  def getLabelsContaining(self, regex):
    rtn = []
    for label in self.labels:
      if re.match(regex, label, re.DOTALL | re.IGNORECASE):
        rtn.append(label)
    return rtn

  def getLabelsMatching(self, regex):
    return self.getLabelsContaining(regex + '\Z')

  def hasLabelContaining(self, regex):
    for label in self.labels:
      if re.search(regex, label, re.DOTALL | re.IGNORECASE):
        return True
    return False

  def hasLabelMatching(self, regex):
    return self.hasLabelContaining(regex + '\Z')

  def hasLabel(self, value):
    for label in self.labels:
      if label.lower() == value.lower():
        return True
    return False

  def hasCc(self, value):
    for cc in self.cc:
      if cc.lower() == value.lower():
        return True
    return False
