# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging
from features import component_helpers
from framework import jsonfeed
from tracker import tracker_bizobj


class ComponentPredict(jsonfeed.JsonFeed):
  def HandleRequest(self, mr):
    text = mr.request.POST.items()[0][1]
    logging.info('text: %r', text)

    prediction = {'components': []}
    component_id = component_helpers.PredictComponent(text)
    if component_id:
      config = self.services.config.GetProjectConfig(
          self.mr.cnxn, self.mr.project_id)
      component = tracker_bizobj.FindComponentDefByID(component_id, config)
      prediction['components'].append(component.path)
    logging.info('prediction: %r', str(prediction))

    return prediction
