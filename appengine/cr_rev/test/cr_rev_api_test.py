# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

import endpoints
from appengine.utils import testing
from appengine.cr_rev import cr_rev_api
from appengine.cr_rev import models

from protorpc import protojson


class TestCrRevApi(testing.AppengineTestCase):
  # restricted=False is needed for testing.
  app_module = endpoints.api_server(
      [cr_rev_api.CrRevApi], restricted=False)

  @staticmethod
  def _create_repo():
    my_repo = models.Repo()
    my_repo.name = 'cool_src'
    my_repo.project = 'cool'
    my_repo.numberings = [
        models.Numbering(
          numbering_type=models.NumberingType.SVN,
          numbering_identifier='svn://svn.cool.org/cool_src/trunk/src'),
        models.Numbering(
          numbering_type=models.NumberingType.COMMIT_POSITION,
          numbering_identifier='refs/heads/master'),
    ]
    my_repo.first_commit = 'd76246ce726e2817d3b5443e64ca5511cf2eaa92'
    my_repo.latest_commit = '5891fc79aebc68c276159568984d0798be1f92ff'
    return my_repo

  @staticmethod
  def _convert_json_to_model_proto(model, js):
    """Convert a dict returned by a JSON API into a protorpc message."""
    return protojson.decode_message(model.ProtoModel(), json.dumps(js))

  def _convert_items_to_protos(self, model, response_json):
    """Convert the 'items' section of a JSON API into protorpc messages."""
    items = response_json['items']
    response_json['items']  = [self._convert_json_to_model_proto(model, item)
                               for item in items]
    return response_json

  def test_empty_repo(self):
    """Test that calling repo.list yields an empty list with no data."""
    response = self.test_app.post_json('/_ah/spi/CrRevApi.get_repos', {})
    self.assertEqual('200 OK', response.status)
    expected = {}
    self.assertEqual(expected, response.json)

  def test_repo_list(self):
    """Test that calling repo.list yields an list of scanned repos."""
    my_repo = self._create_repo()
    my_repo.put()
    second_repo = self._create_repo()
    second_repo.name = 'cooler_src'
    second_repo.put()

    response = self.test_app.post_json('/_ah/spi/CrRevApi.get_repos', {})
    self.assertEqual('200 OK', response.status)

    expected = {u'items': [
      my_repo.ToMessage(),
      second_repo.ToMessage(),
    ]}

    resp = self._convert_items_to_protos(models.Repo, response.json)
    self.assertEqual(expected, resp)
