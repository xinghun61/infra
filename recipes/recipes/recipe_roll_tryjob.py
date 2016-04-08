# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Rolls recipes.cfg dependencies."""

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'file',
  'url',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]

from recipe_engine.recipe_api import Property

import collections
import re
import base64
import json


def get_auth_token(api, service_account=None):
  """
  Get an auth token; this assumes the user is logged in with the infra
  authutil command line utility.

  If service_account is provided, that service account will be used when calling
  authutil.
  """
  cmd = ['/opt/infra-tools/authutil', 'token']
  if service_account: # pragma: no cover
      cmd.extend([
          '-service-account-json='
          '/creds/service_accounts/service-account-%s.json' % service_account])

  result = api.step(
      'Get auth token', cmd,
      stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output('ya29.foobar'))
  return result.stdout.strip()

def parse_protobuf(lines): # pragma: no cover
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
    if text == 'true':
      return True
    if text == 'false':
      return False
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

    raise ValueError('Could not understand line: <%s>' % line)
  return ret

def get_project_config(api, project, headers=None):
  """Fetch the project config from luci-config.

  Args:
    project: The name of the project in luci-config.
    auth_token: Authentication token to use when talking to luci-config.

  Returns:
    The recipes.cfg file for that project, as a parsed dictionary. See
    parse_protobuf for details on the format to expect.
  """
  url = 'https://luci-config.appspot.com/_ah/api/config/v1/config_sets/'
  url += api.url.quote('projects/%s/refs/heads/master' % project, safe='')
  url += '/config/recipes.cfg'

  fetch_result = api.url.fetch(url, step_name='Get %s deps' % project,
                               headers=headers)
  result = json.loads(fetch_result)

  file_contents = base64.b64decode(result['content'])
  parsed = parse_protobuf(file_contents.split('\n'))
  return parsed


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

def get_url_mapping(api, headers=None):
  """Fetch the mapping of project id to url from luci-config.

  Args:
    headers: Optional authentication headers to pass to luci-config.

  Returns:
    A dictionary mapping project id to its luci-config project spec (among
    which there is a repo_url key).
  """
  url = 'https://luci-config.appspot.com/_ah/api/config/v1/projects'

  fetch_result = api.url.fetch(url, step_name='Get project urls',
      headers=headers,
      step_test_data=lambda: api.raw_io.test_api.output(json.dumps({
             'projects': [
                 {
                     'repo_type': 'GITILES',
                     'id': 'recipe_engine',
                     'repo_url': 'https://repo.repo/recipes-py',
                 },
                 {
                     'repo_type': 'GITILES',
                     'id': 'build',
                     'repo_url': 'https://repo.repo/chromium/build',
                 }
             ],
      })))
  mapping = {}

  for project in json.loads(fetch_result)['projects']:
    project = {str(k): str(v) for k, v in project.items()}
    mapping[project['id']] = project
  return mapping


RietveldPatch = collections.namedtuple(
    'RietveldPatch', 'project server issue patchset')


def parse_patches(api, patches_raw, rietveld, issue, patchset, patch_project):
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
      api.python.failing_step(
          "Invalid patchset list",
          "You have two patches for %r. Patches seen so far: %r" % (
              project, result)
      )

    result[project] = RietveldPatch(project, server, issue, patchset)

  return result

def simulation_test(api, proj, proj_config, repo_path, deps):
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

  return api.python(
      '%s tests' % proj, recipes_py_loc, args, stdout=api.raw_io.output())


def checkout_projects(api, all_projects, url_mapping,
                      downstream_projects, root_dir, patches):
  """Checks out projects listed in all_projects into root_dir, applying patches

  Args:
    all_projects: All the projects we care about.
    url_mapping: Project id to url of git repository.
    downstream_projects: The mapping from project to projecst that depend on it.
    root_dir: Root directory to check this project out in.
    patches: Mapping of project id to patch to apply to that project.

  Returns:
    The projects we want to test, and the locations of those projects
  """
  # TODO(martiniss): be smarter about which projects we actually run tests on

  # All the projects we want to test.
  projs_to_test  = set()
  # Projects we need to look at dependencies for.
  queue = set(all_projects)
  # luci config project name to file system path of the checkout
  locations = {}

  while queue:
    proj = queue.pop()
    if proj not in projs_to_test:
      locations[proj] = checkout_project(
          api, proj, url_mapping[proj], root_dir, patches.get(proj))
      projs_to_test.add(proj)

    for downstream in downstream_projects[proj]:
        queue.add(downstream)

  return projs_to_test, locations

def checkout_project(api, proj, proj_config, root_dir, patch=None):
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
  api.file.makedirs('%s directory' % proj, repo_path)

  # Not working yet, but maybe??
  #api.file.rmtree('clean old %s repo' % proj, checkout_path)

  config = api.gclient.make_config(
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

  api.bot_update.ensure_checkout(**kwargs)
  return repo_path


PROJECTS_TO_TRY = [
  'build',
  'build_limited_scripts_slave',
  'recipe_engine',
  'depot_tools',
]

PROPERTIES = {
  'patches': Property(kind=str, param_name='patches_raw', default="",
                      help="Patches to apply. Format is"
                      "project1:https://url.to.codereview/123456#ps01 where"
                      "url.to.codereview is the address of the code review site"
                      ", 123456 is the issue number, and ps01 is the patchset"
                      "number"),
  # This recipe can be used as a tryjob by setting the rietveld, issue, and
  # patchset properties, like a normal tryjob. If those are set, it will use
  # those, as well as any data sent in the regular properties, as patches to
  # apply.
  "rietveld": Property(kind=str, default="",
                       help="The Rietveld instance the issue is from"),
  "issue": Property(kind=str, default=None,
                    help="The Rietveld issue number to pull data from"),
  "patchset": Property(kind=str, default=None,
                       help="The patchset number for the supplied issue"),
  "patch_project": Property(
      kind=str, default=None,
      help="The luci-config name of the project this patch belongs to"),

  # To generate an auth token for running locally, run
  #   infra/go/bin/authutil login
  'auth_token': Property(
      default=None, help="The auth_token to use to talk to luci-config. "
      "Mutually exclusive with the service_account property"),
  'service_account': Property(
      default=None, kind=str,
      help="The name of the service account to use when running on a bot. For "
           "example, if you use \"recipe-roller\", this recipe will try to use "
           "the /creds/service_accounts/service-account-recipe-roller.json "
           "service account")
}

def RunSteps(api, patches_raw, rietveld, issue, patchset, patch_project,
             auth_token, service_account):
  # TODO(martiniss): use real types
  issue = int(issue) if issue else None
  patchset = int(patchset) if patchset else None

  if not auth_token:
    auth_token = get_auth_token(api, service_account)
  else: # pragma: no cover
    assert not service_account, (
        "Only one of \"service_account\" and \"auth_token\" may be set")

  headers = {'Authorization': 'Bearer %s' % auth_token}

  patches = parse_patches(
      api, patches_raw, rietveld, issue, patchset, patch_project)

  root_dir = api.path['slave_build']

  url_mapping = get_url_mapping(api, headers)

  # luci config project name to recipe config namedtuple
  recipe_configs = {}

  # List of all the projects we care about testing. luci-config names
  all_projects = set(p for p in url_mapping if p in PROJECTS_TO_TRY)

  recipe_configs = {
      p: get_project_config(api, p, headers) for p in all_projects}

  deps, downstream_projects = get_deps_info(all_projects, recipe_configs)

  projs_to_test, locations = checkout_projects(
      api, all_projects, url_mapping, downstream_projects, root_dir, patches)

  with api.step.defer_results():
    for proj in projs_to_test:
      deps_locs = {dep: locations[dep] for dep in deps[proj]}

      simulation_test(
          api, proj, recipe_configs[proj], locations[proj], deps_locs)


def GenTests(api):
  def make_recipe_config(name, deps):
    # Deps should be a list of project ids
    config = [
        'api_version: 1',
        'project_id: "%s"' % name,
        'recipes_path: ""',
    ]
    for dep in deps:
      config += [
        'deps {',
        '  project_id: "%s"' % dep,
        '  url: "https://repo.url/foo.git"',
        '  branch: "master"',
        '  revision: "deadbeef"',
        '}',
      ]
    return base64.b64encode('\n'.join(config))

  def project(name, deps=None):
    if not deps:
      deps = []
    return api.raw_io.output(json.dumps({
            "content": make_recipe_config(name, deps),
            "content_hash": "v1:814564d6e6507ad7de56de8c76548a31633ce3e4",
            "revision": "80abb4d6f37e89ba0786c5bca9c599565693fe12",
            "kind": "config#resourcesItem",
            # NOTE: Invalid etag, truncated for line length.
            "etag": "\"-S_IMdk0_sAeij2f-EAhBG43QvQ/JlXgwF3XIs6IVH1\""
    }))

  yield (
      api.test('basic') +
      api.step_data("Get build deps", project('build')) +
      api.step_data("Get recipe_engine deps", project('recipe_engine'))
  )

  yield (
      api.test('one_patch') +
      api.step_data("Get build deps", project('build')) +
      api.step_data("Get recipe_engine deps", project('recipe_engine')) +
      api.properties(patches="build:https://fake.code.review/123456#ps1")
  )

  yield (
      api.test('bad_patches') +
      api.properties(
          patches="build:https://f.e.w/1#ps1,build:https://f.e.w/1#ps1")
  )

  yield (
      api.test('deps') +
      api.step_data("Get build deps", project('build', ['recipe_engine'])) +
      api.step_data("Get recipe_engine deps", project('recipe_engine'))
  )

  yield (
      api.test('tryjob') +
      api.properties(
        rietveld="https://fake.code.review",
        issue='12345678',
        patchset='1',
        patch_project="build",
      ) +
      api.step_data("Get build deps", project('build', ['recipe_engine'])) +
      api.step_data("Get recipe_engine deps", project('recipe_engine'))
  )

