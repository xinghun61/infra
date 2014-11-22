# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from appengine_module.trooper_o_matic import controller
from appengine_module.trooper_o_matic import models

# pylint: disable=R0201,C0322

package = 'TrooperOMatic'


### Api response classes..

class CqProjectStats(messages.Message):
  single_run_data = messages.MessageField(
      models.CqStat.ProtoModel(), 1, repeated=True)
  queue_time_data = messages.MessageField(
      models.CqTimeInQueueForPatchStat.ProtoModel(), 2, repeated=True)
  total_time_data = messages.MessageField(
      models.CqTotalTimeForPatchStat.ProtoModel(), 3, repeated=True)


### Api methods.

@endpoints.api(name='trooper_o_matic', version='v1')
class TrooperOMaticAPI(remote.Service):
  """TrooperOMatic API v1."""

  PROJECT_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      project=messages.StringField(1, required=True))

  @endpoints.method(PROJECT_RESOURCE_CONTAINER, CqProjectStats,
      path='cq_stats/{project}', name='cq_stats.get')
  def cq_stats_get(self, request):
    cq_stats = controller.get_cq_stats(request.project)
    single_run_data = [x.ToMessage() for x in cq_stats['single_run_data']]
    queue_time_data = [x.ToMessage() for x in cq_stats['queue_time_data']]
    total_time_data = [x.ToMessage() for x in cq_stats['total_time_data']]
    return CqProjectStats(
        single_run_data=single_run_data,
        queue_time_data=queue_time_data,
        total_time_data=total_time_data,
    )

  @models.BuildSLOOffender.query_method(  # pragma: no cover
      path='build_slo_offenders', name='build_slo_offenders.list',
      query_fields=('limit', 'pageToken', 'tree', 'master', 'builder'))
  def get_build_slo_offenders(self, query):
    return query.order(-models.BuildSLOOffender.generated)


APPLICATION = endpoints.api_server([TrooperOMaticAPI])
