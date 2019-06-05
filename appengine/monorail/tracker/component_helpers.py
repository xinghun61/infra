# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for component-related servlets."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging
import re

from proto import tracker_pb2
from tracker import tracker_bizobj


ParsedComponentDef = collections.namedtuple(
    'ParsedComponentDef',
    'leaf_name, docstring, deprecated, '
    'admin_usernames, cc_usernames, admin_ids, cc_ids, '
    'label_strs, label_ids')


def ParseComponentRequest(mr, post_data, services):
  """Parse the user's request to create or update a component definition.

  If an error is encountered then this function populates mr.errors
  """
  leaf_name = post_data.get('leaf_name', '')
  docstring = post_data.get('docstring', '')
  deprecated = 'deprecated' in post_data

  admin_usernames = [
      uname.strip() for uname in re.split('[,;\s]+', post_data['admins'])
      if uname.strip()]
  cc_usernames = [
      uname.strip() for uname in re.split('[,;\s]+', post_data['cc'])
      if uname.strip()]
  all_user_ids = services.user.LookupUserIDs(
      mr.cnxn, admin_usernames + cc_usernames, autocreate=True)

  admin_ids = []
  for admin_name in admin_usernames:
    if admin_name not in all_user_ids:
      mr.errors.member_admins = '%s unrecognized' % admin_name
      continue
    admin_id = all_user_ids[admin_name]
    if admin_id not in admin_ids:
     admin_ids.append(admin_id)

  cc_ids = []
  for cc_name in cc_usernames:
    if cc_name not in all_user_ids:
      mr.errors.member_cc = '%s unrecognized' % cc_name
      continue
    cc_id = all_user_ids[cc_name]
    if cc_id not in cc_ids:
      cc_ids.append(cc_id)

  label_strs = [
    lab.strip() for lab in re.split('[,;\s]+', post_data['labels'])
    if lab.strip()]

  label_ids = services.config.LookupLabelIDs(
      mr.cnxn, mr.project_id, label_strs, autocreate=True)

  return ParsedComponentDef(
      leaf_name, docstring, deprecated,
      admin_usernames, cc_usernames, admin_ids, cc_ids,
      label_strs, label_ids)


def GetComponentCcIDs(issue, config):
  """Return auto-cc'd users for any component or ancestor the issue is in."""
  result = set()
  for component_id in issue.component_ids:
    cd = tracker_bizobj.FindComponentDefByID(component_id, config)
    if cd:
      result.update(GetCcIDsForComponentAndAncestors(config, cd))

  return result


def GetCcIDsForComponentAndAncestors(config, cd):
  """Return auto-cc'd user IDs for the given component and ancestors."""
  result = set(cd.cc_ids)
  ancestors = tracker_bizobj.FindAncestorComponents(config, cd)
  for anc_cd in ancestors:
    result.update(anc_cd.cc_ids)

  return result
