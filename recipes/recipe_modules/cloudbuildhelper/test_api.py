# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from hashlib import sha256

from recipe_engine import recipe_test_api


class CloudBuildHelperTestApi(recipe_test_api.RecipeTestApi):
  def output(self, image, target='target', canonical_tag=None):
    if not image:
      img = 'example.com/fake-registry/%s' % target
      digest = 'sha256:'+sha256(target).hexdigest()[:16]+'...'
      tag = canonical_tag
    else:
      img = image.image
      digest = image.digest
      tag = image.tag

    out = {'view_build_url': 'https://example.com/build/%s' % target}
    if img:
      out['image'] = {'image': img, 'digest': digest, 'tag': tag}
      out['view_image_url'] = 'https://example.com/image/%s' % target

    return self.m.json.output(out)

  def error_output(self, message, target='target'):
    return self.m.json.output({
      'error': message,
      'view_build_url': 'https://example.com/build/%s' % target,
    })
