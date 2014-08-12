# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints
from protorpc import remote

import models  # pylint: disable=W0403


package = 'CrRev'


### Api methods.

@endpoints.api(name='crrev', version='v1')
class CrRevApi(remote.Service):
  """CrRev API v1."""

  # pylint: disable=R0201
  @models.Repo.query_method(path='repos', name='repos.list')
  def get_repos(self, query):
    """List all scanned repositories."""
    return query


APPLICATION = endpoints.api_server([CrRevApi])
