# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parser for a small subset of requirements.txt syntax.

This parser supports only equality requirements. See parse_requirements()
docstring for more details.

Definition of the full requirements.txt syntax can be found at
https://pythonhosted.org/setuptools/pkg_resources.html#requirement-objects
"""

import re


HASH_COMMENT_RE = re.compile(
  r"""
  \#\s+                      # Lines that start with a '#'
  (?P<hash_type>sha1):\s+    # Hash type is hardcoded to be sha1 for now.
  (?P<hash>[a-f0-9]{40})     # Restrict to sha1 hashes
  """, re.X)


PACKAGE_LINE_RE = re.compile(
  r"""
  (?P<package_name>[-A-Za-z0-9_]+)
  \s*==\s*
  (?P<version>[-A-Za-z0-9_.]+)
  """, re.X)


class Requirements(object):
  def __init__(self, package_name, version, hashes=()):
    """Record equality requirement for a package.

    Args:
      package_name (str):
      version (str):
      hashes (iterable of (hash type, hash)): possible hashes for this package.
        hash type is a string giving the name of the hash algorithm (ex. 'sha1')
        hash is the hash itself as a string.
    """
    self.package_name = package_name
    self.version = version
    self.hashes = tuple(hashes)


def parse_requirements(content):
  """Parse the content of a requirement file.

  This function supports a small subset of the standard format as specified on
  https://pythonhosted.org/setuptools/pkg_resources.html#requirement-objects
  Namely, only equality constraints are supported.

  This function also parses comments in search of hashes, in a way compatible
  with what Peep (https://pypi.python.org/pypi/peep) does.

  Example requirements.txt file:

    # sha1: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
    mynicepackage == 1.0

    # linux
    # sha1: 1234beef1234beef1234beef1234beef1234beef
    # windows
    # sla1: 4321dead4321dead4321dead4321dead4321dead
    binary_package == 0.2

  Args:
    content (str): content of a requirement.txt file.

  Returns:
    requirements (list of Requirements): all packages listed in the input, with
      any associated hashes.
  """
  requirements = []
  current_hashes = []
  for line_number, line in enumerate(content.splitlines()):
    line = line.strip()
    if not line:
      # Hashes must be in a comment block connected to the package name
      current_hashes = []
      continue

    match = HASH_COMMENT_RE.match(line)
    if match:
      current_hashes.append((match.groupdict()['hash_type'],
                             match.groupdict()['hash']))
      continue

    if line.startswith('#'):
      continue

    match = PACKAGE_LINE_RE.match(line)
    if match:
      requirements.append(Requirements(match.groupdict()['package_name'],
                                       match.groupdict()['version'],
                                       hashes=current_hashes))
      current_hashes = []
      continue

    raise ValueError('Line %d not understood:\n%s' % (line_number, line))

  return requirements
