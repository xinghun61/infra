
"""Classes that implement the hotlistissues page and related forms."""

from features import hotlist_views
from framework import servlet
from framework import permissions
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
    if mr.hotlist_id is None:
      self.abort(404, 'no hotlist specified')
    with self.profiler.Phase('finishing getting hostlist'):
      hotlist_view = self._GetHotlistView(mr)
      if hotlist_view is None:
        self.abort(404, 'hostlist not found')
    return {
        'hotlist': hotlist_view,
        }

  def _GetHotlistView(self, mr):
    """Retrieve the current hostlist_view."""
    hotlist = self._GetHotlist(mr)
    if hotlist is None:
      return None
    user_emails = self.services.user.LookupUserEmails(
        mr.cnxn, [hotlist.owner_ids[0]])
    hotlist_view = hotlist_views.HotlistView(
        hotlist, mr.auth.user_id, mr.viewed_user_auth.user_id, user_emails)
    return hotlist_view
  #TODO(jojwang): when friendly url is added, loop through hotlist_view's
  #friendly_url and url and decide if hotlist should have
  #view.url = view.friendly_url or view.url = the url with ID

  def _GetHotlist(self, mr):
    """Retrieve the current hotlist."""
    if mr.hotlist_id is None:
      return None
    hotlist = self.services.features.GetHotlist( mr.cnxn, mr.hotlist_id)
    return hotlist
