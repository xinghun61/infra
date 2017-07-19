# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import git as tpp_git
from . import python as tpp_python

from recipe_engine import recipe_test_api


class ThirdPartyPackagesTestApi(recipe_test_api.RecipeTestApi):

  @property
  def git(self):
    return tpp_git

  @property
  def python(self):
    return tpp_python
