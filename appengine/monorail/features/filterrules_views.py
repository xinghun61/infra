# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to display filter rules in templates."""

import logging

from framework import template_helpers


class RuleView(template_helpers.PBProxy):
  """Wrapper class that makes it easier to display a Rule via EZT."""

  def __init__(self, rule_pb, users_by_id):
    super(RuleView, self).__init__(rule_pb)

    self.action_type = ''
    self.action_value = ''

    if rule_pb is None:
      return  # Just leave everything as ''

    # self.predicate is automatically available.

    # For the current UI, we assume that each rule has exactly
    # one action, so we can determine the text value for it here.
    if rule_pb.default_status:
      self.action_type = 'default_status'
      self.action_value = rule_pb.default_status
    elif rule_pb.default_owner_id:
      self.action_type = 'default_owner'
      self.action_value = users_by_id[rule_pb.default_owner_id].email
    elif rule_pb.add_cc_ids:
      self.action_type = 'add_ccs'
      usernames = [users_by_id[cc_id].email for cc_id in rule_pb.add_cc_ids]
      self.action_value = ', '.join(usernames)
    elif rule_pb.add_labels:
      self.action_type = 'add_labels'
      self.action_value = ', '.join(rule_pb.add_labels)
    elif rule_pb.add_notify_addrs:
      self.action_type = 'also_notify'
      self.action_value = ', '.join(rule_pb.add_notify_addrs)
    elif rule_pb.warning:
      self.action_type = 'warning'
      self.action_value = rule_pb.warning
    elif rule_pb.error:
      self.action_type = 'error'
      self.action_value = rule_pb.error
