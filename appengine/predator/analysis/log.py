# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a customized logger to log information about Predator analysis.

The logger only logs information that clients are interested in."""


from collections import defaultdict
from collections import namedtuple


class Message(namedtuple('Message', ['name', 'message'])):

  def ToDict(self):
    return {self.name: self.message}


class Log(object):

  def __init__(self):
    self.info_log = []
    self.warning_log = []
    self.error_log = []

  def info(self, name, message):
    self.info_log.append(Message(name, message))

  def warning(self, name, message):
    self.warning_log.append(Message(name, message))

  def error(self, name, message):
    self.error_log.append(Message(name, message))

  def ToDict(self):
    log = defaultdict(dict)
    for info_message in self.info_log:
      log['info'].update(info_message.ToDict())

    for warning_message in self.warning_log:
      log['warning'].update(warning_message.ToDict())

    for error_message in self.error_log:
      log['error'].update(error_message.ToDict())

    return log
