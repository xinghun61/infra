# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the hotlistissues page and related forms."""

from features import hotlist_views
from features import features_bizobj
from framework import servlet
from framework import permissions
from framework import framework_views
from services import features_svc

class HotlistIssues(servlet.Servlet):
  """HotlistIssues is a page that shows the issues of one hotlist."""

  _PAGE_TEMPLATE = 'features/hotlist-issues-page.ezt'

  def AssertBasePermission(self, mr):
    """Check that the user has permission to even visit this page."""
    super(HotlistIssues, self).AssertBasePermission(mr)
    try:
      hotlist = self._GetHotlist(mr)
    except features_svc.NoSuchHotlistException:
      return
    permit_view = permissions.CanViewHotlist(mr.auth.effective_ids, hotlist)
    if not permit_view:
      raise permissions.PermissionException(
        'User is not allowed to view this hotlist')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly usef info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    with self.profiler.Phase('getting hotlist'):
      if mr.hotlist_id is None:
        self.abort(404, 'no hotlist specified')

    with self.profiler.Phase('making views'):
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user,
          features_bizobj.UsersInvolvedInHotlists([self._GetHotlist(mr)]))
      hotlist_view = self._GetHotlistView(mr, users_by_id)
      # TODO(jojwang): find some better design rather than passing
      # users_by_id into _GetHotlistView

    return {
        'hotlist': hotlist_view,
        }

  def _GetHotlistView(self, mr, users_by_id):
    """Retrieve the current hostlist_view."""
    hotlist = self._GetHotlist(mr)
    if hotlist is None:
      return None
    hotlist_view = hotlist_views.HotlistView(
        hotlist, mr.auth.user_id, mr.viewed_user_auth.user_id,
        users_by_id)
    return hotlist_view
  # TODO(jojwang): when friendly url is added, loop through hotlist_view's
  # friendly_url and url and decide if hotlist should have
  # view.url = view.friendly_url or view.url = the url with ID

  def _GetHotlist(self, mr):
    """Retrieve the current hotlist."""
    if mr.hotlist_id is None:
      return None
    try:
      hotlist = self.services.features.GetHotlist( mr.cnxn, mr.hotlist_id)
      return hotlist
    except features_svc.NoSuchHotlistException:
      self.abort(404, 'hotlist not found')
