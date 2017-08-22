# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to display a message explaining that a project has moved.

When a project moves, we just display a link to the new location.
"""

import logging

from framework import exceptions
from framework import framework_bizobj
from framework import framework_helpers
from framework import servlet
from framework import urls


class ProjectMoved(servlet.Servlet):
  """The ProjectMoved page explains that the project has moved."""

  _PAGE_TEMPLATE = 'sitewide/moved-page.ezt'

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""

    # We are not actually in /p/PROJECTNAME, so mr.project_name is None.
    # Putting the ProjectMoved page inside a moved project would make
    # the redirect logic much more complicated.
    if not mr.specified_project:
      raise exceptions.InputException('No project specified')

    project = self.services.project.GetProjectByName(
        mr.cnxn, mr.specified_project)
    if not project:
      self.abort(404, 'project not found')

    if not project.moved_to:
      # Only show this page for projects that are actually moved.
      # Don't allow hackers to construct misleading links to this servlet.
      logging.info('attempt to view ProjectMoved for non-moved project: %s',
                   mr.specified_project)
      self.abort(400, 'This project has not been moved')

    if framework_bizobj.RE_PROJECT_NAME.match(project.moved_to):
      moved_to_url = framework_helpers.FormatAbsoluteURL(
          mr, urls.SUMMARY, include_project=True, project_name=project.moved_to)
    elif (project.moved_to.startswith('https://') or
          project.moved_to.startswith('http://')):
      moved_to_url = project.moved_to
    else:
      # Prevent users from using javascript: or any other tricky URL scheme.
      moved_to_url = '#invalid-destination-url'

    return {
        'project_name': mr.specified_project,
        'moved_to_url': moved_to_url,
        }
