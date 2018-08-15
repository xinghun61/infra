# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import logging

from api import monorail_servicer
from api import converters
from api.api_proto import features_pb2
from api.api_proto import features_prpc_pb2
from businesslogic import work_env
from features import features_bizobj
from framework import framework_views


class FeaturesServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Features objects.

  Each API request is implemented with a method as defined in the .proto
  file that does any request-specific validation, uses work_env to
  safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = features_prpc_pb2.FeaturesServiceDescription

  @monorail_servicer.PRPCMethod
  def ListHotlistsByUser(self, mc, request):
    """Return the specified project config."""
    user_id = converters.IngestUserRefs(
        mc.cnxn, [request.user], self.services.user)[0]

    with work_env.WorkEnv(mc, self.services) as we:
      # List hotlists for the currently authenticated user.
      hotlists = we.ListHotlistsByUser(user_id)

    with mc.profiler.Phase('making user views'):
      users_involved = features_bizobj.UsersOwnersOfHotlists(hotlists)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    converted_hotlists = [
        converters.ConvertHotlist(hotlist, users_by_id)
        for hotlist in hotlists]

    result = features_pb2.ListHotlistsByUserResponse(
        hotlists=converted_hotlists)

    return result

  @monorail_servicer.PRPCMethod
  def GetHotlistStarCount(self, mc, request):
    """Get the star count for the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      star_count = we.GetHotlistStarCount(hotlist_id)

    result = features_pb2.GetHotlistStarCountResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def StarHotlist(self, mc, request):
    """Star the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      we.StarHotlist(hotlist_id, request.starred)
      star_count = we.GetHotlistStarCount(hotlist_id)

    result = features_pb2.StarHotlistResponse(star_count=star_count)
    return result
