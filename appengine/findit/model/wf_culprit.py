# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model import analysis_status as status
from model.wf_suspected_cl import WfSuspectedCL


class WfCulprit(WfSuspectedCL):
  """Represents a culprit that causes a group of failures on Chromium waterfall.

  'Wf' is short for waterfall.
  """

  # When the code-review of this culprit was notified.
  cr_notification_time = ndb.DateTimeProperty(indexed=True)

  # The status of code-review notification: None, RUNNING, COMPLETED, ERROR.
  cr_notification_status = ndb.IntegerProperty(indexed=True)

  @property
  def cr_notification_processed(self):
    return self.cr_notification_status in (status.COMPLETED, status.RUNNING)

  @property
  def cr_notified(self):
    return self.cr_notification_status == status.COMPLETED
