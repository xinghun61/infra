# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Converts repo dependencies in DEPS into Git submodules.

This module was cloned from the similarly named "resource" of the
sync_submodules recipe module, in order to make it reusable by other
code, and with the plan/expectation that the original should soon be
retired, and its caller use this shared version instead (keep it DRY).

This version of the code uses an instance of the Repo class (from the
infra.libs.git2 package), so it does not require a Git clone with a work
tree, and it doesn't care what its current directory is.
"""

import collections
import json
import logging
import os
import re

import requests

from infra.libs.deps2submodules.deps_utils import EvalDepsContent, ExtractUrl
from infra.libs.deps2submodules.gitlinks import Gitlinks
from infra.libs.git2 import CalledProcessError

# TODO: move to git2/data and import here
SHA1_RE = re.compile(r'[0-9a-fA-F]{40}')
ABBREV_SHA1_RE = re.compile(r'[0-9a-fA-F]{4,39}')

JSON_PREFIX = ")]}'\n"

# The name of the field in the JSON output from Gitiles that
# gives the value of the SHA-1 hash of a revision.
_COMMIT_SHA1_KEY = 'commit'

SubmodData = collections.namedtuple('SubmodData', 'url,revision')

LOGGER = logging.getLogger(__name__)


class Deps2Submodules(object):
  """Parsed/structured representation of DEPS, that can render as submodules.

  Usage: invoke Evaluate() once, and then UpdateSubmodules() as many
  times as desired to reify the resulting gitlinks and .gitmodules
  file into the given repo.
  """

  def __init__(self, deps_contents, refs_resolver,
               path_prefix, extra_submodules=None, _known_refs=None):
    """Creates a new instance.

    @param deps_contents: the (textual) contents of the main DEPS file
    @param refs_resolver: object with a Resolve method for looking up Git refs

    TODO: add a (recurse-)DEPS content retriever
    """
    self._deps_contents = deps_contents
    self._resolver = refs_resolver
    self._path_prefix = path_prefix
    self._named_deps = extra_submodules or []
    # a cache of unlimited size(!)
    self._known_refs = dict(_known_refs) if _known_refs else {}
    self._gitmodules = None  # to be computed by Evaluate()

  def withUpdatedDeps(self, deps_contents):
    """Creates a new instance with new deps file content.

    But is otherwise a clone of the current instance.  This is useful
    in order to let the new instance preserve the benefit of its "known
    refs" cache.
    """
    return Deps2Submodules(deps_contents, self._resolver, self._path_prefix,
                           self._named_deps, self._known_refs)

  def _Sanitize(self, submods):
    """Resolves conflicts in submodule data.

    A conflict is when one submodule's path is a prefix of another's,
    meaning that the latter is a proper subset of the former.  The
    conflict is resolved by ignoring the submodule with the smaller
    subset.
    """
    ret = {}
    for name, value in submods.iteritems():
      if not name.startswith(self._path_prefix):
        # Won't check prefix if disabled path_prefix
        LOGGER.warn('Dropping submodule "%s", because it is outside the '
                    'working directory "%s"', name, self._path_prefix)
        continue

      prefix = self._path_prefix
      # Strip the prefix from the submodule name.
      name_strip_prefix = name[len(prefix):]
      name = name_strip_prefix

      parts = name_strip_prefix.split('/')[:-1]
      while parts:
        may_conflict = prefix + '/'.join(parts)
        if may_conflict in submods:
          LOGGER.warn('Dropping submodule "%s", because it is nested in '
                      'submodule "%s"', name, may_conflict)
          break
        parts.pop()
      else:
        ret[name] = value
    return ret

  def _CollateCurrentDeps(self, deps, prefix_path='.'):
    """Collects one set of deps.

    Returns a dict mapping submodule path/name to its information (encapsuled in
    a SubmodData tuple).
    """

    # TODO: no-op for now; this becomes relevant when recurse-deps processing
    # is (re-)introduced.
    prepend = lambda prefix, fname: os.path.normpath(
        os.path.join(prefix, fname))

    def make_submod_datum(dep):
      if dep is None:
        # Doesn't occur in present-day DEPS files, but does historically.
        return None
      pinned_url = ExtractUrl(dep)
      if not pinned_url:
        return None
      url, hsh = tuple(pinned_url.partition('@')[0::2])
      return SubmodData(url=url, revision=hsh)

    submods = {}
    def accumulate_submods(deps_dict):
      for (path, dep) in deps_dict.iteritems():
        submod_datum = make_submod_datum(dep)
        if not submod_datum:
          continue
        dep_name = prepend(prefix_path, path)
        submods[dep_name] = submod_datum

    # Add the OS-specific deps first, so that the non-specific ones
    # can override them as necessary.
    #
    # TODO: we have now implemented the preferred, general-purpose condition
    # mechanism, so the whole 'deps_os' hack becomes no longer necessary.
    # Remove this when the last of the deps_os items have indeed been
    # eradicated from all DEPS files that we care about.
    #
    # The 'deps_os' item may be absent, and if it's present its 'unix' sub-item
    # may be absent.  (The 'deps' *should* be always be present, but
    # you never know.)
    accumulate_submods(deps.get('deps_os', {}).get('unix', {}))
    accumulate_submods(deps.get('deps', {}))
    return submods

  def _FormatNamedDeps(self):
    """Formats explicitly named deps.

    These are in addition to the deps found in the DEPS file.
    """
    submodules = {}
    for dep in self._named_deps:
      path, url = dep.split('=', 1)
      sha1 = self._Resolve(url, 'refs/heads/master')
      submodules[path] = SubmodData(url=url, revision=sha1)
    return submodules

  def _TryAbbreviatedSha1(self, url, revision):
    """Converts an abbreviated commit hash (SHA-1) to its full, 40-char form."""
    target = '%s/+/%s?format=JSON' % (url, revision)
    r = requests.get(target)
    r.raise_for_status()
    text = r.text
    if not text.startswith(JSON_PREFIX):
      raise Exception(
          'response to %s does not start with JSON prefix' % (target,))
    text = text[len(JSON_PREFIX):]
    props = json.loads(text)
    if _COMMIT_SHA1_KEY in props:
      return props[_COMMIT_SHA1_KEY]
    raise Exception('response to %s lacks expected %s field' %
                    (target, _COMMIT_SHA1_KEY))

  def _Resolve(self, url, revision):
    """Converts revision specifiers to their full, 40-hex-char SHA-1 form.

    Accepts either symbolc ref names, or abbreviated commit hash values.
    """
    ORIGIN = 'origin/'
    if revision.startswith(ORIGIN):
      revision = revision[len(ORIGIN):]

    key = (url, revision)
    if key in self._known_refs:
      # TODO: consider exposing some sort of control to the caller as to the
      # use/lifetime of this cache.  As used by gsubmodd, it saves a lot of time
      # during initial loading; but if used on a long-running service it means
      # we could miss updates.
      sha1 = self._known_refs[key]
    else:
      sha1 = self._resolver.Resolve(url, revision)
      if not sha1 and ABBREV_SHA1_RE.match(revision):
        sha1 = self._TryAbbreviatedSha1(url, revision)
      self._known_refs[key] = sha1
    if sha1:
      return sha1
    raise Exception('%s does not have a ref named %s' % (url, revision))

  def _ResolveRefs(self, deps_list):
    """Resolves symbolic refs and duplicated submodule names."""
    results = collections.OrderedDict()

    for submods in deps_list:
      for name, data in sorted(submods.iteritems()):
        url = data.url
        revision = data.revision

        if not revision:
          revision = 'master'

        if not SHA1_RE.match(revision):
          sha1 = self._Resolve(url, revision)
          data = SubmodData(url=url, revision=sha1)

        results.pop(name, None)
        results[name] = data
    return results

  def _RenderConfig(self, submodules):
    """Renders content suitable for a .gitmodules file.

    Uses format compatible with Git submodules subsystem.
    """
    result_lines = []
    for name, data in submodules.iteritems():
      url = data.url
      result_lines.extend([
          '[submodule "%s"]' % name,
          '\tpath = %s' % name,
          '\turl = %s' % url])
    return '\n'.join(result_lines) + '\n'

  def Evaluate(self):
    """Analyzes dependencies, resolving refs and eliminating conflicts.

    The result of the analysis is retained in member variable _gitmodules, in
    the form of a 2-tuple consisting of the .gitmodules file content (a string),
    and some submodule definitions.  The submodule definitions are in the form
    of a dict of path => SubmodData.  (Reminder: the dict is actually an
    OrderedDict; but remember that the "order" refers to order of insertion, not
    lexicographical order!)
    """
    # Collect deps info from content of original DEPS file
    submods = self._CollateCurrentDeps(EvalDepsContent(self._deps_contents))
    # Add "hard-coded" (psuedo-)deps passed in explicitly
    submods.update(self._FormatNamedDeps())

    # TODO: implement recurse-deps (and _Sanitize() them too).  For
    # now, no one is using it.  Thus at the moment _deps_list has exactly
    # one item.
    deps_list = [self._Sanitize(submods)]

    submodules = self._ResolveRefs(deps_list)
    # TODO: it might be better to defer the file rendering til the last minute,
    # mostly because it means the thing we hold on to is less complex, and so
    # easier to reason about.
    gitmodules_file_content = self._RenderConfig(submodules)
    self._gitmodules = (gitmodules_file_content, submodules)

  def UpdateSubmodules(self, repo, origin_commit):
    """Writes a current version of .gitmodules file, and updates gitlinks.

    Relies on previously evaluated DEPS file content.

    Returns the hash of a Git tree object for the root of the tree rebuilt
    with the added .gitmodules file and all the gitlinks defined in it.
    """
    assert self._gitmodules, ('Attempted UpdateSubmodules '
                             'without having called Evaluate()')
    gitmodules_file, submodule_data = self._gitmodules
    hsh = repo.intern(gitmodules_file)
    repo.run('update-index',
             '--add', '--cacheinfo', '100644', hsh, '.gitmodules')

    return Gitlinks(repo, hsh, submodule_data, origin_commit).BuildRootTree()


class GitRefResolver(object):
  """Ref resolver that operates on a Git repo wrapped in a Repo object."""

  def __init__(self, repo):
    self._repo = repo

  def Resolve(self, url, ref):
    """Converts a symbolic ref to a SHA-1 hash from the given repo.

    NB: this method resolves refs as of the *current* time when this
    code runs, rather than at the time the ref appeared in a DEPS file.  Usually
    the difference is inconsequential.  However, when this code is used for an
    initial load of a long repo history it could of course be quite different.

    Note that since commits have timestamps we could eliminate the
    long discrepancy (at least reduce it to a trivial amount), although it's
    unclear whether the benefit justifies the significant effort/complexity.
    """
    try:
      output = self._repo.run('ls-remote', '--exit-code', url, ref)
    except CalledProcessError as err:
      if err.returncode == 2:
        return None
      raise  # pragma: no cover
    return output.split()[0]
