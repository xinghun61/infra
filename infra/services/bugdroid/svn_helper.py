# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import subprocess
import xml.etree.cElementTree as etree


class svn_path(object):
  def __init__(self, kind, action, filename, copy_from_path=None,
               copy_from_rev=None):
    self.kind = kind
    self.action = action
    self.filename = filename
    self.copy_from_path = copy_from_path
    self.copy_from_rev = copy_from_rev


class svn_log_entry(object):
  def __init__(self, revision, date, author, msg):
    self.scm = 'svn'
    self.revision = revision
    self.date = date
    self.author = author
    self.msg = msg
    self.paths = []

  def add_path(self, kind, action, filename, copy_from_path, copy_from_rev):
    self.paths.append(svn_path(kind, action, filename, copy_from_path,
                                 copy_from_rev))

  def __str__(self):
    rtn = ('------------------------------------------------------------------'
           '------\n')
    rtn += 'r%d | %s | %s\n\n' % (self.revision, self.author, self.date)
    rtn += 'Changed paths:\n'
    for path in self.paths:
        rtn += '   %s %s\n' % (path.action, path.filename)
    rtn += '\n%s\n' % self.msg
    rtn += ('-----------------------------------------------------------------'
            '-------')
    return rtn


def get_svn_log_entries(svn_url, limit=10, min_rev=None):
  params = ['svn', 'log', '--xml', '-v']
  if min_rev:
    params.append('-r')
    params.append('%d:HEAD' % min_rev)

  if limit:
    params.append('-l')
    params.append(str(limit))

  params.append(svn_url)

  log_text = subprocess.check_output(params)

  if log_text:
    return get_svn_log_entries_alt(log_text)

  return []


def get_svn_log_entries_alt(log_text):
  log_xml = etree.XML(log_text)

  svn_logs = []

  for child in log_xml.getchildren():

    slog = svn_log_entry(int(child.attrib['revision']), child.findtext('date'),
                         child.findtext('author'),
                         child.findtext('msg').encode("utf-8"))
    paths = child.find('paths')
    for path in paths.getchildren():
      copy_from_path = path.get('copyfrom-path', None)
      copy_from_rev = path.get('copyfrom-rev', None)

      slog.add_path(path.attrib['kind'], path.attrib['action'], path.text,
                    copy_from_path, copy_from_rev)
    svn_logs.append(slog)

  return svn_logs


def get_branch(svn_log_entry_obj, full=False):
  for path in svn_log_entry_obj.paths:
    m = re.search("/branches/(?:chromium/)?(.*?)/", path.filename,
                  re.IGNORECASE)
    if m:
      if full:
        return m.group(0)
      else:
        return m.group(1)
  return None