# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Backend for Chrome UI Catalog when running on App Engine."""

import httplib
import os
import re
import sys
import webapp2

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import gae_ts_mon
from pylib.third_party import cloudstorage
from pylib.ui_catalogue import routes_list
from pylib.ui_catalogue import ScreenshotLoader


class RemoteScreenshotLoader(ScreenshotLoader):
  """Remote version of ScreenshotLoader."""

  def get_data(self, data_location):
    """Read the (JSON) screenshot description.

    Args:
      data_location: the path or URL of the screenshots description. This must
      be a the URL of a Google Cloud Storage object.

    Returns:
      A set of screenshot descriptions
    """

    # All the current bots put the results in the same bucket. Make sure that
    # any requested GCS data comes from this bucket.
    # TODO: Find a better way of configuring the bucket without code changes.
    RESULT_DETAILS_BUCKET = 'chromium-result-details'
    matches = re.match(
        r'https://storage.cloud.google.com(/%s/.*)' % RESULT_DETAILS_BUCKET,
        data_location)
    if not matches:
      raise ScreenshotLoader.ScreenshotLoaderException
    cloudstorage_name = matches.group(1)
    try:
      with cloudstorage.open(cloudstorage_name) as f:
        descriptions = f.read()
    except cloudstorage.Error:
      raise ScreenshotLoader.ScreenshotLoaderException
    return ScreenshotLoader._read_descriptions(data_location, descriptions)


gae_app = webapp2.WSGIApplication(routes_list, debug=True)
gae_ts_mon.initialize(gae_app)
gae_app.config['screenshot_loader'] = RemoteScreenshotLoader()
