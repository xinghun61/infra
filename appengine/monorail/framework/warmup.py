# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to handle the initial warmup request from AppEngine."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from framework import jsonfeed


class Warmup(jsonfeed.InternalTask):
  """Placeholder for warmup work.  Used only to enable min_idle_instances."""

  def HandleRequest(self, _mr):
    """Don't do anything that could cause a jam when many instances start."""
    logging.info('/_ah/startup does nothing in Monorail.')
    logging.info('However it is needed for min_idle_instances in app.yaml.')

    return {
      'success': 1,
      }

class Start(jsonfeed.InternalTask):
  """Placeholder for start work.  Used only to enable manual_scaling."""

  def HandleRequest(self, _mr):
    """Don't do anything that could cause a jam when many instances start."""
    logging.info('/_ah/start does nothing in Monorail.')
    logging.info('However it is needed for manual_scaling in app.yaml.')

    return {
      'success': 1,
      }


class Stop(jsonfeed.InternalTask):
  """Placeholder for stop work.  Used only to enable manual_scaling."""

  def HandleRequest(self, _mr):
    """Don't do anything that could cause a jam when many instances start."""
    logging.info('/_ah/stop does nothing in Monorail.')
    logging.info('However it is needed for manual_scaling in app.yaml.')

    return {
      'success': 1,
      }
