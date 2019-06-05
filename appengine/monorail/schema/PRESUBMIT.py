# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Presubmit script just for Monorail's SQL files."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


def AlterTableCheck(input_api, output_api):  # pragma: no cover
  this_dir = input_api.PresubmitLocalPath()
  sql_files = set(x for x in input_api.os_listdir(this_dir)
                  if (x.endswith('.sql') and x != 'queries.sql'))
  log_file = input_api.os_path.join(this_dir, 'alter-table-log.txt')
  affected_files = set(f.LocalPath() for f in input_api.AffectedTextFiles())

  if (any(f in affected_files for f in sql_files) ^
      (log_file in affected_files)):
    return [output_api.PresubmitPromptOrNotify(
        'It looks like you have modified the sql schema without updating\n'
        'the alter-table-log, or vice versa. Are you sure you want to do this?')
    ]
  return []


def CheckChangeOnUpload(input_api, output_api):  # pragma: no cover
  output = AlterTableCheck(input_api, output_api)
  return output


def CheckChangeOnCommit(input_api, output_api):  # pragma: no cover
  output = AlterTableCheck(input_api, output_api)
  return output
