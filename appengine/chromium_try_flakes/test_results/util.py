# Copyright (C) 2015 Google Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


def normalize_test_type(test_type, ignore_with_patch=False):
  """Clean extra details added to the test type.

  Args:
    test_type: String, step name containing test type.

  Returns:
    Test type without platforms and other noise.
  """
  # We allow (with patch) as a separate test_type for now since executions of
  # uncommitted code should be treated differently.
  if not ignore_with_patch:
    patched = ' (with patch)' in test_type
    test_type = test_type.replace(' (with patch)', '', 1)

  # Special rule for instrumentation tests.
  if test_type.startswith('Instrumentation test '):
    test_type = test_type[len('Instrumentation test '):]

  # Clean out any platform noise. For simplicity and based on current data
  # we just keep everything before the first space, e.g. base_unittests.
  first_space = test_type.find(' ')
  if first_space != -1:
    test_type = test_type[:first_space]

  if not ignore_with_patch and patched:
    return '%s (with patch)' % test_type
  return test_type


def flatten_tests_trie(tests_trie, delimiter):
  """Flattens tests trie structure.

  The tests trie structure is described in
  https://www.chromium.org/developers/the-json-test-results-format (see
  top-level 'tests' key).

  Args:
    test_trie: Test trie (value of the 'tests' key in JSON results).
    delimiter: Delimiter to use for concatenating parts of test name.

  Returns:
    Dictionary mapping full test names to dict describing them, which contains
    at least 'expected' and 'actual' fields.
  """
  flattened_tests = {}
  for prefix, node in tests_trie.iteritems():
    if 'expected' in node and 'actual' in node:  # leaf node
      new_node = node.copy()
      new_node['actual'] = new_node['actual'].split(' ')
      new_node['expected'] = new_node['expected'].split(' ')
      flattened_tests[prefix] = new_node
    else:
      for name, test in flatten_tests_trie(node, delimiter).iteritems():
        flattened_tests[prefix + delimiter + name] = test

  return flattened_tests
