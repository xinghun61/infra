# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail features."""

from features import features_constants
from protorpc import messages


class Hotlist(messages.Message):
  """This protocol buffer holds all the metadata associated with a hotlist."""
  # A numeric identifier for this hotlist.
  hotlist_id = messages.IntegerField(1, required=True)

  # The short identifier for this hotlist.
  name = messages.StringField(2, required=True)

  # A one-line summary (human-readable) of the hotlist.
  summary = messages.StringField(3, default='')

  # A detailed description of the hotlist.
  description = messages.StringField(4, default='')

  # Hotlists can be marked private to prevent unwanted users from seeing them.
  is_private = messages.BooleanField(5, default=False)

  # Note that these lists are disjoint (a user ID will not appear twice).
  owner_ids = messages.IntegerField(6, repeated=True)
  editor_ids = messages.IntegerField(8, repeated=True)
  follower_ids = messages.IntegerField(9, repeated=True)


  class HotlistItem(messages.Message):
    """Nested message for a hotlist to issue relation."""
    issue_id = messages.IntegerField(1, required=True)
    rank = messages.IntegerField(2, required=True)
    adder_id = messages.IntegerField(3)
    date_added = messages.IntegerField(4)
    note = messages.StringField(5, default='')

  items = messages.MessageField(HotlistItem, 10, repeated=True)

  # The default columns to show on hotlist issues page
  default_col_spec = messages.StringField(11, default=features_constants.DEFAULT_COL_SPEC)

def MakeHotlist(name, hotlist_item_fields=None, **kwargs):
  """Returns a hotlist protocol buffer with the given attributes.
    Args:
      hotlist_item_fields: tuple of (iid, rank, user, date, note)
  kwargs should only include the following:
    hotlist_id, summary, description, is_private, owner_ids, editor_ids,
    follower_ids, default_col_spec"""
  hotlist = Hotlist(name=name, **kwargs)

  if hotlist_item_fields is not None:
    for iid, rank, user, date, note in hotlist_item_fields:
      hotlist.items.append(Hotlist.HotlistItem(
          issue_id=iid, rank=rank, adder_id=user, date_added=date, note=note))

  return hotlist


# For any issues that were added to hotlists before we started storing that
# timestamp, just use the launch date of the feature as a default.
ADDED_TS_FEATURE_LAUNCH_TS = 1484350000  # Jan 13, 2017


def MakeHotlistItem(issue_id, rank=None, adder_id=None, date_added=None, note=None):
  item = Hotlist.HotlistItem(
      issue_id=issue_id,
      date_added=date_added or ADDED_TS_FEATURE_LAUNCH_TS)
  if rank is not None:
    item.rank = rank
  if adder_id is not None:
    item.adder_id = adder_id
  if note is not None:
    item.note = note
  return item
