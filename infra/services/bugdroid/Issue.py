# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import re


class changelist(list):

  def __init__(self, seq=()):
    list.__init__(self, seq)
    self.added = set()
    self.removed = set()

  def append(self, p_object):
    list.append(self, p_object)
    if p_object in self.removed:
      self.removed.remove(p_object)
    else:
      self.added.add(p_object)

  def remove(self, value):
    list.remove(self, value)

    if value in self.added:
      self.added.remove(value)
    else:
      self.removed.add(value)

  def isChanged(self):
    return (len(self.added) + len(self.removed)) > 0

  def reset(self):
    self.added.clear()
    self.removed.clear()


class Issue2(object):
  
  def __init__(self):
    self.blocking = None
    self.blocked_on = None
    self.body = None
    self.depends_on = None
    self.cc = changelist()
    self.closed = None
    self.comment = ''
    self.created = None
    self.id = 0
    self.labels = changelist()
    self.merged_into = None
    self.open = False
    self.owner = None
    self.reporter = None
    self.status = None
    self.stars = 0
    self.summary = None
    self.updated = None

    self.dirty = False
    self.new = True
    self.itm = None
    self.project_name = None
    self.comments = None
    self.comment_count = 0
    self.first_comment = None
    self.last_comment = None
    self.changed = set()

  def __getattribute__(self, item):
    if item in ['body'] and not object.__getattribute__(self, item):
      comment = self.getFirstComment()
      self.__setattr__(item, comment.comment)

    return object.__getattribute__(self, item)

  def __setattr__(self, name, value):
    self.__dict__[name] = value
    if 'changed' in self.__dict__:
      self.__dict__['changed'].add(name)

    #Automatically set the project name if the itm is set
    if name == 'itm' and value and hasattr(value, 'project_name'):
      self.__dict__['project_name'] = value.project_name

    #Treat comments and dirty flag specially
    if name not in ('dirty', 'body', 'comments', 'itm', 'new',
                    'comment_count', 'first_comment','last_comment',
                    'project_name', 'changed'):
      self.__dict__['dirty'] = True
    if name in ('dirty') and not value:
      self.labels.reset()
      self.cc.reset()
      if 'changed' in self.__dict__:
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
      if re.match(regex + '\Z', label, re.DOTALL | re.IGNORECASE):
        rtn.append(label)
    return rtn

  def getLabelsMatching(self, regex):
    rtn = []
    for label in self.labels:
      if re.match(regex, label, re.DOTALL | re.IGNORECASE):
        rtn.append(label)
    return rtn
  
  def hasLabelContaining(self, regex):
    for label in self.labels:
      if re.search(regex, label, re.DOTALL | re.IGNORECASE):
        return True
    return False

  def hasLabelMatching(self, regex):
    for label in self.labels:
      if re.match(regex + '\Z', label, re.DOTALL | re.IGNORECASE):
        return True
    return False

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

  def getComments(self):
    if not self.comments and self.itm:
      self.comments = self.itm.getComments(self.id)
      self.comment_count = len(self.comments)
    return self.comments

  def getFirstComment(self):
    if not self.first_comment and self.itm:
      self.first_comment = self.itm.getFirstComment(self.id)
    return self.first_comment

  def getLastComment(self):
    if not self.last_comment and self.itm:
      self.last_comment = self.itm.getLastComment(self.id)
    return self.last_comment

  def getCommentCount(self):
    if not self.comment_count and self.itm:
      self.comment_count = self.itm.getCommentCount(self.id)
    return self.comment_count

  def save(self, send_email=True):
    if self.itm:
      self.itm.save(self, send_email)

  def refresh(self):
    if self.itm:
      self.comments = None
      self.last_comment = None
      self.comment_count = 0
      self.itm.refresh(self)
    return self

  def __getstate__(self):
    """This method ensures that we don't pickle the itm (which has will
    raise an exception due to the way the apiary folks did their information
    (i.e. OAuth kicking us once again).
    """
    odict = self.__dict__.copy()
    del odict['itm']
    return odict

  def __setstate__(self, dictionary):
    self.__dict__.update(dictionary)
    self.itm = None
