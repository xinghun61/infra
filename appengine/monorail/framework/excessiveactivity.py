# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display the an error page for excessive activity.

This page is shown when the user performs a given type of action
too many times in a 24-hour period or exceeds a lifetime limit.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from framework import servlet


class ExcessiveActivity(servlet.Servlet):
  """ExcessiveActivity page shows an error message."""

  _PAGE_TEMPLATE = 'framework/excessive-activity-page.ezt'

  def GatherPageData(self, _mr):
    """Build up a dictionary of data values to use when rendering the page."""
    return {}
