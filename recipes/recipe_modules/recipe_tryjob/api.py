# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import hashlib
import json
import re

from recipe_engine import recipe_api

#TODO(martiniss): make the recipe engine be able to dump the package as JSON so
# we don't have to do this weird parsing.
def parse_protobuf(lines):
  """Parse the protobuf text format just well enough to understand recipes.cfg.

  We don't use the protobuf library because we want to be as self-contained
  as possible in this bootstrap, so it can be simply vendored into a client
  repo.

  We assume all fields are repeated since we don't have a proto spec to work
  with.

  Args:
    lines: a list of the lines to parse
  Returns:
    A recursive dictionary of lists.
  """
  def parse_atom(text):
    # NOTE: Assuming we only have numbers and strings to avoid using
    # ast.literal_eval
    try:
      return int(text)
    except ValueError:
      return text.strip("'").strip('"')

  ret = {}
  while lines:
    line = lines.pop(0).strip()

    m = re.match(r'(\w+)\s*:\s*(.*)', line)
    if m:
      ret.setdefault(m.group(1), []).append(parse_atom(m.group(2)))
      continue

    m = re.match(r'(\w+)\s*{', line)
    if m:
      subparse = parse_protobuf(lines)
      ret.setdefault(m.group(1), []).append(subparse)
      continue

    if line == '}':
      return ret
    if line == '':
      continue

    raise ValueError('Could not understand line: <%s>' % line)# pragma: no cover
  return ret

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
  # We want to test B and C, if A changes. Recipe projects only know about he
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
    result[patch_project] = RietveldPatch(
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
]

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
      auth_token: Authentication token to use when talking to luci-config.

    Returns:
      The recipes.cfg file for that project, as a parsed dictionary. See
      parse_protobuf for details on the format to expect.
    """
    result = self.m.luci_config.get_project_config(project, 'recipes.cfg')

    parsed = parse_protobuf(result['content'].split('\n'))
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
    # TODO(martiniss): be smarter about which projects we actually run tests on

    # All the projects we want to test.
    projs_to_test  = set()
    # Projects we need to look at dependencies for.
    queue = set(patches.keys())
    # luci config project name to file system path of the checkout
    locations = {}

    while queue:
      proj = queue.pop()
      if proj not in projs_to_test:
        locations[proj] = self._checkout_project(
            proj, url_mapping[proj], root_dir, patches.get(proj))
        projs_to_test.add(proj)

        for downstream in downstream_projects[proj]:
          queue.add(downstream)
        for upstream in deps[proj]:
          queue.add(upstream)

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
    repo_path = checkout_path.join(proj)
    self.m.file.makedirs('%s directory' % proj, repo_path)

    # Not working yet, but maybe??
    #api.file.rmtree('clean old %s repo' % proj, checkout_path)

    config = self.m.gclient.make_config(
        GIT_MODE=True, CACHE_DIR=root_dir.join("__cache_dir"))
    soln = config.solutions.add()
    soln.name = proj
    soln.url = proj_config['repo_url']

    kwargs = {
        'suffix': proj,
        'gclient_config': config,
        'force': True,
        'cwd': checkout_path,
    }
    if patch:
      kwargs['rietveld'] = patch.server
      kwargs['issue'] = patch.issue
      kwargs['patchset'] = patch.patchset
    else:
      kwargs['patch'] = False

    self.m.bot_update.ensure_checkout(**kwargs)
    return repo_path


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
    args = []
    for dep_name, location in deps.items():
      args += ['-O', '%s=%s' % (dep_name, location)]
    args += ['--package', repo_path.join('infra', 'config', 'recipes.cfg')]

    args += ['simulation_test']

    return self._python('%s tests' % proj, recipes_py_loc, args)

  def _python(self, name, script, args, **kwargs):
    """Call python from infra's virtualenv.

    This is needed because of the coverage module, which is not installed by
    default, but which infra's python has installed."""
    return self.m.step(name, [
        self.m.path['checkout'].join('ENV', 'bin', 'python'),
        '-u', script] + args, **kwargs)

  def run_tryjob(self, patches_raw, rietveld, issue, patchset, patch_project):
    patches = parse_patches(
        self.m.python.failing_step, patches_raw, rietveld, issue, patchset,
        patch_project)

    root_dir = self.m.path['slave_build']

    # Needed to set up the infra checkout, for _python
    self.m.gclient.set_config('infra')
    self.m.gclient.c.solutions[0].revision = 'origin/master'
    self.m.gclient.checkout()
    self.m.gclient.runhooks()

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

    projs_to_test, locations = self._checkout_projects(
        root_dir, url_mapping, deps, downstream_projects, patches)

    with self.m.step.defer_results():
      for proj in projs_to_test:
        deps_locs = {dep: locations[dep] for dep in deps[proj]}

        self.simulation_test(
            proj, recipe_configs[proj], locations[proj], deps_locs)
