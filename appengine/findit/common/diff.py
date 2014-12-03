# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class ChangeType(object):
  ADD = 'add'
  DELETE = 'delete'
  MODIFY = 'modify'
  COPY = 'copy'
  RENAME = 'rename'


def IsKnownChangeType(change_type):
  return change_type in [ChangeType.ADD, ChangeType.DELETE, ChangeType.MODIFY,
                         ChangeType.COPY, ChangeType.RENAME]
