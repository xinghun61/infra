"""Issue object for working with issue tracker issues"""

import copy
import re
from issue_tracker.change_tracking_list import ChangeTrackingList
from issue_tracker.utils import parseDateTime

class Issue(object):
  def __init__(self, issue_entry):
    self.id = issue_entry.get('id')

    self.blocked_on = [e['issueId'] for e in issue_entry.get('blockedOn', [])]
    self.blocking = [e['issueId'] for e in issue_entry.get('blocking', [])]

    self.merged_into = issue_entry.get('mergedInto', {}).get('issueId')

    self.created = parseDateTime(issue_entry.get('published'))
    self.updated = parseDateTime(issue_entry.get('updated'))

    if issue_entry.get('closed', []):
      self.closed = parseDateTime(issue_entry.get('closed', []))
    else:
      self.closed = None

    self.summary = issue_entry.get('summary')
    self.description = issue_entry.get('description')
    self.reporter = issue_entry.get('author', {}).get('name')
    self.owner = issue_entry.get('owner', {}).get('name')
    self.status = issue_entry.get('status')
    self.stars = issue_entry.get('stars')
    self.open = issue_entry.get('state') == 'open'
    self.labels = ChangeTrackingList(issue_entry.get('labels', []))
    self.cc = ChangeTrackingList([e['name'] for e in issue_entry.get('cc', [])])

    self.dirty = False

  def __setattr__(self, name, value):
    self.__dict__.setdefault('dirty', False)
    self.__dict__.setdefault('changed', set())

    # If dirty flag was reset to false.
    if name == 'dirty' and not value:
      self.__dict__['labels'].reset()
      self.__dict__['cc'].reset()
      self.__dict__['changed'].clear()
      self.__dict__['dirty'] = value
    else:
      self.__dict__[name] = value
      self.__dict__['dirty'] = True
      self.__dict__['changed'].add(name)

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
