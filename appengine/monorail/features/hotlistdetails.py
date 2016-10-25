# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlets for hotlist details main subtab."""

import time

from third_party import ezt

from framework import framework_helpers
from framework import servlet
from framework import permissions
from framework import urls

_MSG_DESCRIPTION_MISSING = 'Description is missing.'
_MSG_SUMMARY_MISSING = 'Summary is missing.'
_MSG_NAME_MISSING = 'Hotlist name is missing.'
_MSG_COL_SPEC_MISSING = 'Hotlist default columns are missing.'


class HotlistDetails(servlet.Servlet):
  """A page with hotlist details and editing options."""

  _PAGE_TEMPLATE = 'features/hotlist-details-page.ezt'

  def AssertBasePermission(self, mr):
    super(HotlistDetails, self).AssertBasePermission(mr)
    if not permissions.CanViewHotlist(mr.auth.effective_ids, mr.hotlist):
      raise permissions.PermissionException(
          'User is not allowed to view the hotlist details')

  def GatherPageData(self, mr):
    """Buil up a dictionary of data values to use when rendering the page."""
    cant_administer_hotlist = not permissions.CanAdministerHotlist(
        mr.auth.effective_ids, mr.hotlist)

    return {
        'initial_summary': mr.hotlist.summary,
        'initial_description': mr.hotlist.description,
        'initial_name': mr.hotlist.name,
        'initial_default_col_spec': mr.hotlist.default_col_spec,
        'initial_is_private': ezt.boolean(mr.hotlist.is_private),
        'cant_administer_hotlist': ezt.boolean(cant_administer_hotlist),
        }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    (summary, description, name, default_col_spec) = self._ParseMetaData(
        post_data, mr.errors)
    is_private = post_data.get('is_private') != 'no'

    if not mr.errors.AnyErrors():
      self.services.features.UpdateHotlist(
          mr.cnxn, mr.hotlist.hotlist_id, name=name, summary=summary,
          description=description, is_private=is_private,
          default_col_spec=default_col_spec)

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_summary=summary, initial_description=description,
          initial_name=name, initial_default_col_spec=default_col_spec)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, '/u/%s/hotlists/%s%s' % (
              mr.auth.user_id, mr.hotlist_id, urls.HOTLIST_DETAIL),
          saved=1, ts=int(time.time()),
          include_project=False)

  def _ParseMetaData(self, post_data, errors):
    """Process a POST on the hotlist metadata."""
    summary = None
    description = None
    name = None
    default_col_spec = None

    if 'summary' in post_data:
      summary = post_data['summary']
      if not summary:
        errors.summary = _MSG_SUMMARY_MISSING
    if 'description' in post_data:
      description = post_data['description']
      if not description:
        errors.description = _MSG_DESCRIPTION_MISSING
    if 'name' in post_data:
      name = post_data['name']
      if not name:
        errors.name = _MSG_NAME_MISSING
    if 'default_col_spec' in post_data:
      default_col_spec = post_data['default_col_spec']
    return summary, description, name, default_col_spec
