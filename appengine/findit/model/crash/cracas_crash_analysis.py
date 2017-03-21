# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import urllib

from model.crash.chrome_crash_analysis import ChromeCrashAnalysis

_PLATFORM_TO_PRODUCT_NAME = {'win': 'Chrome',
                             'mac': 'Chrome_Mac',
                             'ios': 'Chrome_iOS',
                             'linux': 'Chrome_Linux'}

_CRACAS_BASE_URL = 'https://crash.corp.google.com/browse'


class CracasCrashAnalysis(ChromeCrashAnalysis):
  """Represents an analysis of a Chrome crash on Cracas."""

  @property
  def crash_url(self):  # pragma: no cover
    product_name = _PLATFORM_TO_PRODUCT_NAME.get(self.platform)
    query = ('product.name=\'%s\' AND custom_data.ChromeCrashProto.'
             'magic_signature_1.name=\'%s\' AND '
             'custom_data.ChromeCrashProto.channel=\'%s\'') % (
                 product_name, self.signature, self.platform)
    return _CRACAS_BASE_URL + '?' + urllib.urlencode(
        {'q': query}).replace('+', '%20')
