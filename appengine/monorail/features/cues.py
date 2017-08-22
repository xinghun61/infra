# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Simple servlet to store the fact that a user has dismissed a cue card.

Cue cards are small on-page help items that appear when the user has
done a certain action or is viewing a project that is in a certain
state.  The cue card give the user a suggestion of what he/she should
do next.  Cue cards can be dismissed to reduce visual clutter on the
page once the user has learned the content of the suggestion.  That
preference is recorded in the User PB, and the same cue card will not
be presented again to the same user.

Exmple: The logged in user has dismissed the cue card that tells him/her how
to search for numbers in the issue tracker:

  POST /hosting/cues.do
    cue_id=search_for_numbers&token=12344354534
"""


import logging

from framework import exceptions
from framework import jsonfeed


class SetCuesFeed(jsonfeed.JsonFeed):
  """A class to process an AJAX request to dismiss a cue card."""

  def HandleRequest(self, mr):
    """Processes a user's POST request to dismiss a cue card.

    Args:
      mr: commonly used info parsed from the request.
    """

    cue_id = mr.GetParam('cue_id')
    if not cue_id:
      raise exceptions.InputException('no cue_id specified')

    logging.info('Handling user set cue request: %r', cue_id)
    new_dismissed_cues = mr.auth.user_pb.dismissed_cues
    new_dismissed_cues.append(cue_id)
    self.services.user.UpdateUserSettings(
        mr.cnxn, mr.auth.user_id, mr.auth.user_pb,
        dismissed_cues=new_dismissed_cues)

