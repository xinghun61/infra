# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# TODO(http://crbug.com/660462): this needs to actually do something.
# pylint: disable=E0711, W0613, R0201
class CodeReview(object):  # pragma: no cover
  """An interface to interact with code review."""

  def PostMessage(self, codereview_url, message):
    """Posts the given message to the CL codereview of the specified url.

    Args:
      codereview_url(str): The url to a CL codereview.
      message(str): The message to be posted to the codereview.
    """
    raise NotImplemented()
