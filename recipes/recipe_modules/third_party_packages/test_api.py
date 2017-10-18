# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import gcloud as tpp_gcloud
from . import git as tpp_git
from . import python as tpp_python
from . import ninja as tpp_ninja
from . import cmake as tpp_cmake
from . import swig as tpp_swig
from . import go as tpp_go

from recipe_engine import recipe_test_api


class ThirdPartyPackagesTestApi(recipe_test_api.RecipeTestApi):

  @property
  def gcloud(self):
    return tpp_gcloud

  @property
  def git(self):
    return tpp_git

  @property
  def python(self):
    return tpp_python

  @property
  def ninja(self):
    return tpp_ninja

  @property
  def cmake(self):
    return tpp_cmake

  @property
  def swig(self):
    return tpp_swig

  @property
  def go(self):
    return tpp_go
