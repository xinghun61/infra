# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
The tree list is stored in the app engine datastore. Currently it is manually
created by an administrator.
"""

import datetime
import alerts
import webapp2

from components import auth
from protorpc import messages
from protorpc import message_types
from protorpc import remote

import endpoints

import utils

from google.appengine.api import users
from google.appengine.ext import ndb

package = 'TreeList'

class TreeMessage(messages.Message):
  """Proto message for a Tree

  Used only as request and response types for the endpoints API"""
  name = messages.StringField(1)
  display_name = messages.StringField(2)
  bug_labels = messages.StringField(3, repeated=True)
  group = messages.StringField(4, default='*')

class Tree(ndb.Model):
  # key is the tree name e.g. "chromium".

  # luci-auth group this tree belongs to e.g. "googlers"
  group = ndb.StringProperty(default='*')
  # Name to display on the left hand side e.g. "Chromium"
  display_name = ndb.StringProperty(indexed=False)
  # Bug labels relevant to this tree e.g. "gardening-blink"
  bug_labels = ndb.StringProperty(repeated=True, indexed=False)

  def to_proto(self):
    return TreeMessage(
        name=self.key.string_id(),
        group=self.group,
        display_name=self.display_name,
        bug_labels=self.bug_labels)


class TreeListHandler(auth.AuthenticatingHandler):
  GROUPS = ["*", "googlers"]

  def send_json_headers(self):
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.headers['Content-Type'] = 'application/json'

  # Has no 'request' member.
  # Has no 'response' member.
  # pylint: disable=E1002
  @auth.public
  def get(self):
    # Require users to be logged to see builder alerts from private/internal
    # trees.
    queries = []
    for grp in filter(auth.is_group_member, self.GROUPS):
      queries.append(Tree.query(Tree.group == grp).fetch_async())

    all_trees = []
    for trees in queries:
      all_trees.extend(trees.get_result())

    # So that chromium is the default
    all_trees.sort(key=lambda t: not t.key.string_id() == "chromium")

    serialized = [{
        'name': tree.key.string_id(),
        'display_name': tree.display_name,
        'bug_labels': tree.bug_labels,
    } for tree in all_trees]

    data = utils.generate_json_dump({'trees': serialized})
    self.send_json_headers()
    self.response.write(data)

list_app = webapp2.WSGIApplication([
    ('/tree-list', TreeListHandler)])

@auth.endpoints_api(
    name="tree", version="v1",
    title="Tree Service")
class TreeEndpointsApi(remote.Service):
  """API for editing the tree list."""

  @auth.endpoints_method(
      TreeMessage, TreeMessage,
      path="new", http_method='POST')
  @auth.public
  def new(self, request):
    """Add a new tree."""
    if not auth.is_admin():
      raise endpoints.NotFoundException()

    if Tree.get_by_id(request.name):
      raise endpoints.ForbiddenException(
          "Duplicate tree with name '%s' found." % (request.name))

    tree = Tree(
        id=request.name,
        display_name=request.display_name,
        bug_labels=request.bug_labels,
        group=request.group)
    tree.put()
    return tree.to_proto()

  ADD_BUG_LABEL_RESOURCE = endpoints.ResourceContainer(
      tree=messages.StringField(1, required=True),
      label=messages.StringField(2, required=True))

  @auth.endpoints_method(
      ADD_BUG_LABEL_RESOURCE, TreeMessage,
      path="{tree}/add_bug_label", http_method='POST')
  @auth.public
  def add_bug_label(self, request):
    """Add a new bug label to a tree."""
    if not auth.is_admin():
      raise endpoints.NotFoundException()

    tree = Tree.get_by_id(request.tree)
    if not tree:
      raise endpoints.NotFoundException("Tree '%s' not found." % request.tree)

    tree.bug_labels.append(request.label)
    tree.bug_labels = list(set(tree.bug_labels))
    tree.put()
    return tree.to_proto()

endpoints_app = endpoints.api_server([TreeEndpointsApi])
