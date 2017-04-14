# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import hashlib
import json
import re

from recipe_engine import recipe_api

RECIPE_TRYJOB_BYPASS_REASON_TAG = "Recipe-Tryjob-Bypass-Reason"

RECIPE_DEV_WORKFLOW_DOC_LINK = (
    'https://chromium.googlesource.com/external/github.com/luci/recipes-py/+/'
    'master/doc/workflow.md')

def get_recipes_path(project_config):
  # Returns a tuple of the path components to traverse from the root of the repo
  # to get to the directory containing recipes.
  return project_config['recipes_path'][0].split('/')


def get_deps(project_config):
  """ Get the recipe engine deps of a project from its recipes.cfg file. """
  # "[0]" Since parsing makes every field a list
  return [dep['project_id'][0] for dep in project_config.get('deps', [])]


def get_deps_info(projects, configs):
  """Calculates dependency information (forward and backwards) given configs."""
  deps = {p: get_deps(configs[p]) for p in projects}

  # Figure out the backwards version of the deps graph. This allows us to figure
  # out which projects we need to test given a project. So, given
  #
  #     A
  #    / \
  #   B   C
  #
  # We want to test B and C, if A changes. Recipe projects only know about the
  # B-> A and C-> A dependencies, so we have to reverse this to get the
  # information we want.
  downstream_projects = collections.defaultdict(set)
  for proj, targets in deps.items():
    for target in targets:
      downstream_projects[target].add(proj)

  return deps, downstream_projects


RietveldPatch = collections.namedtuple(
    'RietveldPatch', 'project server issue patchset')


def parse_patches(failing_step, patches_raw, rietveld, issue, patchset,
                  patch_project):
  """
  gives mapping of project to patch
    expect input of
    project1:https://a.b.c/1342342#ps1,project2:https://d.ce.f/1231231#ps1
  """
  result = {}

  if rietveld and issue and patchset and patch_project:
    # convert to str because recipes don't like unicode as step names
    result[str(patch_project)] = RietveldPatch(
        patch_project, rietveld, issue, patchset)

  if not patches_raw:
    return result

  for patch_raw in patches_raw.split(','):
    project, url = patch_raw.split(':', 1)
    server, issue_and_patchset = url.rsplit('/', 1)
    issue, patchset = issue_and_patchset.split('#')
    patchset = patchset[2:]

    if project in result:
      failing_step(
          "Invalid patchset list",
          "You have two patches for %r. Patches seen so far: %r" % (
              project, result)
      )

    result[project] = RietveldPatch(project, server, issue, patchset)

  return result



PROJECTS_TO_TRY = [
  'build',
  'build_limited_scripts_slave',
  'recipe_engine',
  'depot_tools',
  'chromium',
]

PROJECT_TO_CONTINUOUS_WATERFALL = {
  'build': 'https://build.chromium.org/p/chromium.tools.build/builders/'
    'recipe-simulation_trusty64',
  'recipe_engine': 'https://build.chromium.org/p/chromium.infra/builders/'
    'recipe_engine-recipes-tests',
  'depot_tools': 'https://build.chromium.org/p/chromium.infra/builders/'
    'depot_tools-recipes-tests',
  'build_limited_scripts_slave': (
    'https://uberchromegw.corp.google.com/i/internal.infra/builders/'
    'build-limited-recipe-tests'),
}

FILE_BUG_FOR_CONTINUOUS_LINK = 'https://goo.gl/PoAPOJ'


class RecipeTryjobApi(recipe_api.RecipeApi):
  """
  This is intended as a utility module for recipe tryjobs. Currently it's just a
  refactored version of a recipe; eventually some of this, especially the
  dependency information, will probably get moved into the recipe engine.
  """
  def _get_project_config(self, project):
    """Fetch the project config from luci-config.

    Args:
      project: The name of the project in luci-config.

    Returns:
      The recipes.cfg file for that project, as a parsed dictionary. See
      parse_protobuf for details on the format to expect.
    """
    result = self.m.luci_config.get_project_config(project, 'recipes.cfg')

    parsed = self.m.luci_config.parse_textproto(result['content'].split('\n'))
    return parsed

  def _checkout_projects(self, root_dir, url_mapping, deps,
                        downstream_projects, patches):
    """Checks out projects listed in projects into root_dir.

    Args:
      root_dir: Root directory to check this project out in.
      url_mapping: Project id to url of git repository.
      downstream_projects: The mapping from project to dependent projects.
      patches: Mapping of project id to patch to apply to that project.

    Returns:
      The projects we want to test, and the locations of those projects
    """
    # Projects we need to look at dependencies for.
    queue = set(patches.keys())
    # Projects we need to checkout, but not test
    to_checkout = set()
    # All the projects we want to test.
    projs_to_test  = set(queue)
    # luci config project name to file system path of the checkout
    locations = {}

    while queue:
      proj = queue.pop()
      if proj not in locations:
        locations[proj] = self._checkout_project(
            proj, url_mapping[proj], root_dir, patches.get(proj))
        projs_to_test.add(proj)

        for downstream in downstream_projects[proj]:
          queue.add(downstream)
        for upstream in deps.get(proj, set()):
          to_checkout.add(upstream)

    while to_checkout:
      proj = to_checkout.pop()
      if proj not in locations:
        locations[proj] = self._checkout_project(
            proj, url_mapping[proj], root_dir, patches.get(proj))
        for upstream in deps[proj]:
          to_checkout.add(upstream)

    return projs_to_test, locations

  def _checkout_project(self, proj, proj_config, root_dir, patch=None):
    """
    Args:
      proj: luci-config project name to checkout.
      proj_config: The recipes.cfg configuration for the project.
      root_dir: The temporary directory to check the project out in.
      patch: optional patch to apply to checkout.

    Returns:
      Path to repo on disk.
    """
    checkout_path = root_dir.join(proj)
    self.m.file.makedirs('%s directory' % proj, checkout_path)

    # Not working yet, but maybe??
    #api.file.rmtree('clean old %s repo' % proj, checkout_path)

    config = self.m.gclient.make_config(CACHE_DIR=root_dir.join("__cache_dir"))
    soln = config.solutions.add()
    soln.name = proj
    soln.url = proj_config['repo_url']

    kwargs = {
        'suffix': proj,
        'gclient_config': config,
    }
    if patch:
      kwargs['rietveld'] = patch.server
      kwargs['issue'] = patch.issue
      kwargs['patchset'] = patch.patchset
    else:
      kwargs['patch'] = False

    with self.m.step.context({'cwd': checkout_path}):
      self.m.bot_update.ensure_checkout(**kwargs)
    return checkout_path.join(proj)

  def get_fail_build_info(self, downstream_projects, patches):
    fail_build = collections.defaultdict(lambda: True)

    for proj, patch in patches.items():
      patch_url = "%s/%s" % (patch.server, patch.issue)
      desc = self.m.git_cl.get_description(
          patch=patch_url, codereview='rietveld', suffix=proj)

      assert desc.stdout is not None, "CL %s had no description!" % patch_url

      bypass_reason = self.m.tryserver.get_footer(
          RECIPE_TRYJOB_BYPASS_REASON_TAG, patch_text=desc.stdout)

      fail_build[proj] = not bool(bypass_reason)

    # Propogate Falses down the deps tree
    queue = list(patches.keys())
    while queue:
      item = queue.pop(0)

      if not fail_build[item]:
        for downstream in downstream_projects.get(item, []):
          fail_build[downstream] = False
          queue.append(downstream)

    return fail_build

  def simulation_test(self, proj, proj_config, repo_path, deps):
    """
    Args:
      proj: The luci-config project to simulation_test.
      proj_config: The recipes.cfg configuration for the project.
      repo_path: The path to the repository on disk.
      deps: Mapping from project name to Path. Passed into the recipes.py
        invocation via the "-O" options.

    Returns the result of running the simulation tests.
    """
    recipes_path = get_recipes_path(proj_config) + ['recipes.py']
    recipes_py_loc = repo_path.join(*recipes_path)
    args = ['--use-bootstrap']
    for dep_name, location in deps.items():
      args += ['-O', '%s=%s' % (dep_name, location)]
    args += ['--package', repo_path.join('infra', 'config', 'recipes.cfg')]

    args += ['test', 'run']

    return self.m.python('%s tests' % proj, recipes_py_loc, args)

  def run_tryjob(self, patches_raw, rietveld, issue, patchset, patch_project):
    patches = parse_patches(
        self.m.python.failing_step, patches_raw, rietveld, issue, patchset,
        patch_project)

    root_dir = self.m.path['start_dir']

    url_mapping = self.m.luci_config.get_projects()

    # TODO(martiniss): use luci-config smarter; get recipes.cfg directly, rather
    # than in two steps.
    # luci config project name to recipe config namedtuple
    recipe_configs = {}

    # List of all the projects we care about testing. luci-config names
    all_projects = set(p for p in url_mapping if p in PROJECTS_TO_TRY)

    recipe_configs = {
        p: self._get_project_config(p) for p in all_projects}

    deps, downstream_projects = get_deps_info(all_projects, recipe_configs)
    should_fail_build_mapping = self.get_fail_build_info(
        downstream_projects, patches)

    projs_to_test, locations = self._checkout_projects(
        root_dir, url_mapping, deps, downstream_projects, patches)

    bad_projects = []
    for proj in projs_to_test:
      deps_locs = {dep: locations[dep] for dep in deps[proj]}

      try:
        result = self.simulation_test(
          proj, recipe_configs[proj], locations[proj], deps_locs)
      except recipe_api.StepFailure as f:
        result = f.result
        if should_fail_build_mapping.get(proj, True):
          bad_projects.append(proj)
      finally:
        link = PROJECT_TO_CONTINUOUS_WATERFALL.get(proj)
        if link:
          result.presentation.links['reference builder'] = link
        # no cover because at the moment we don't test anything which isn't
        # included in PROJECT_TO_TRY, and all those projects have reference
        # builders.
        else: #pragma: no cover
          result.presentation.links[
              'no reference builder; file a bug to get one?'] = (
                  FILE_BUG_FOR_CONTINUOUS_LINK)


    if bad_projects:
      try:
        self.m.python.failing_step(
            'failed tests', "One or more projects failed tests: %r" % (
              ','.join(bad_projects)))
      except self.m.step.StepFailure as f:
        f.result.presentation.links['Confused? README here'] = (
            RECIPE_DEV_WORKFLOW_DOC_LINK)
        raise



