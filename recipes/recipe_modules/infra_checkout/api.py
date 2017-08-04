# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

# DEFAULT_NAMED_CACHE shared across various builders.
DEFAULT_NAMED_CACHE = 'infra_gclient_with_go'


class InfraCheckoutApi(recipe_api.RecipeApi):
  """Stateless API for using public infra gclient checkout."""

  def checkout(self, gclient_config_name, patch_root,
               path=None, named_cache=DEFAULT_NAMED_CACHE, **kwargs):
    """Fetches infra gclient checkout into a given path OR named_cache.

    Arguments:
      * gclient_config_name (string) - name of gclient config.
      * patch_root (path or string) - path **inside** infra checkout to git repo
        in which to apply the patch. For example, 'infra/luci' for luci-py repo.
      * path (path or string) - path to where to create/update infra checkout.
        If None (default) - path is cache with customizable name (see below).
      * named_cache - if path is None, this allows to customize the name of the
        cache. Defaults to DEFAULT_NAMED_CACHE.
        Note: your cr-buildbucket.cfg should specify named_cache for swarming to
          prioritize bots which actually have this cache populated by prior
          runs. Otherwise, using named cache isn't particularly useful, unless
          your pool of builders is very small.
      * kwargs - passed as is to bot_update.ensure_checkout.

    Returns:
      a Checkout object with commands for common actions on infra checkout.
    """
    assert gclient_config_name, gclient_config_name
    assert patch_root, patch_root
    path = path or self.m.path['cache'].join(named_cache)
    self.m.file.ensure_directory('ensure builder dir', path)

    with self.m.context(cwd=path):
      self.m.gclient.set_config(gclient_config_name)
      bot_update_step = self.m.bot_update.ensure_checkout(
          patch_root=patch_root, **kwargs)

    class Checkout(object):
      @property
      def path(self):
        return path

      @property
      def bot_update_step(self):
        return bot_update_step

      @property
      def patch_root_path(self):
        return path.join(patch_root)

      @staticmethod
      def commit_change():
        with self.m.context(cwd=path.join(patch_root)):
          self.m.git(
              '-c', 'user.email=commit-bot@chromium.org',
              '-c', 'user.name=The Commit Bot',
              'commit', '-a', '-m', 'Committed patch',
              name='commit git patch')

      @staticmethod
      def gclient_runhooks():
        with self.m.context(cwd=path):
          self.m.gclient.runhooks()

      @staticmethod
      def ensure_go_env():
        with self.m.context(cwd=path):
          return self.m.python(
              'init infra go env',
              path.join('infra', 'go', 'env.py'), ['go', 'version'],
              infra_step=True)

      @staticmethod
      def go_env_step(*args, **kwargs):
        # name lazily defaults to first two args, like "go test".
        name = kwargs.pop('name', None) or ' '.join(map(str, args[:2]))
        with self.m.context(cwd=path):
          return self.m.python(name, path.join('infra', 'go', 'env.py'),
                               args, **kwargs)

    return Checkout()
