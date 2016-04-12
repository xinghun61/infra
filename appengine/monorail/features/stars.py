# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""This is a starring servlet for users and projects."""

import logging

from framework import jsonfeed
from framework import monorailrequest

USER_STARS_SCOPE = 'users'
PROJECT_STARS_SCOPE = 'projects'


class SetStarsFeed(jsonfeed.JsonFeed):
  """Process an AJAX request to (un)set a star on a project or user."""

  def HandleRequest(self, mr):
    """Retrieves the star persistence object and sets a star."""
    starrer_id = mr.auth.user_id
    item = mr.GetParam('item')  # a project name or a user ID number
    scope = mr.GetParam('scope')
    starred = bool(mr.GetIntParam('starred'))
    logging.info('Handling user set star request: %r %r %r %r',
                 starrer_id, item, scope, starred)

    if scope == PROJECT_STARS_SCOPE:
      project = self.services.project.GetProjectByName(mr.cnxn, item)
      self.services.project_star.SetStar(
          mr.cnxn, project.project_id, starrer_id, starred)

    elif scope == USER_STARS_SCOPE:
      user_id = int(item)
      self.services.user_star.SetStar(mr.cnxn, user_id, starrer_id, starred)

    else:
      raise monorailrequest.InputException('unexpected star scope: %s' % scope)

    return {
        'starred': starred,
        }
