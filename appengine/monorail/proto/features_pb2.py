# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail features."""

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

  class HotlistIssue(messages.Message):
    """Nested message for a hotlist to issue relation."""
    issue_id = messages.IntegerField(1, required=True)
    rank = messages.IntegerField(2, required=True)

  iid_rank_pairs = messages.MessageField(HotlistIssue, 10, repeated=True)

  # The default columns to show on hotlist issues page
  default_col_spec = messages.StringField(11, default='')


def MakeHotlist(name, iid_rank_pairs=None, **kwargs):
  """Returns a hotlist protocol buffer with the given attributes.
  kwargs should only include the following:
    hotlist_id, summary, description, is_private, owner_ids, editor_ids,
    follower_ids, default_col_spec"""
  hotlist = Hotlist(name=name, **kwargs)
  
  if iid_rank_pairs is not None:
    for (issue_id, rank) in iid_rank_pairs:
      hotlist.issues.append(Hotlist.HotlistIssue(issue_id=issue_id, rank=rank))

  return hotlist


def MakeHotlistIssue(issue_id, rank=None):
  issue = Hotlist.HotlistIssue(issue_id=issue_id)
  if rank is not None:
    issue.rank = rank
  
  return issue
