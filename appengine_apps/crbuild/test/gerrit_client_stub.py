# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Stub for Gerrit client."""

import logging

from gerrit.client import Change, Owner, Revision


# pylint: disable=W0613, W0622, R0201
class GerritClientStub(object):
  def __init__(self, *args, **kwargs):
    pass

  test_revision = Revision(
      commit='aaaaabbbbbaaaaabbbbbaaaaabbbbbaaaaabbbbb',
      number=1,
      fetch_ref='refs/changes/123/1',
  )
  test_revision2 = Revision(
      commit='cccccdddddcccccdddddcccccdddddcccccddddd',
      number=2,
      fetch_ref='refs/changes/123/2',
  )
  test_change = Change(
      id='project~master~I7c1811882cf59c1dc55018926edb6d35295c53b2',
      change_id='I7c1811882cf59c1dc55018926edb6d35295c53b2',
      project='project',
      branch='master',
      subject='subject',
      owner=Owner(
          name='John Doe',
          email='johndoe@chromium.org',
          username='johndoe',
      ),
      current_revision=test_revision.commit,
      revisions=[test_revision, test_revision2],
  )

  def get_change(self, change_id, include_all_revisions=True,
                 include_owner_details=False):
    return self.test_change

  def set_review(self, *args, **kwargs):
    logging.info('set_review(*%s, **%s)' % (args, kwargs))
