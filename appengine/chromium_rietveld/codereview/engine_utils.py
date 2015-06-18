# Copyright 2015 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helper functions for engine."""


# NOTE: The SplitPatch function is here because it's needed in models and
# engine. This avoids circular imports as engine also needs models.
# NOTE: The SplitPatch function is duplicated in upload.py, keep them in sync.
def SplitPatch(data):
  """Splits a patch into separate pieces for each file.

  Args:
    data: A string containing the output of svn diff.

  Returns:
    A list of 2-tuple (filename, text) where text is the svn diff output
      pertaining to filename.
  """
  patches = []
  filename = None
  diff = []
  for line in data.splitlines(True):
    new_filename = None
    if line.startswith('Index:'):
      _, new_filename = line.split(':', 1)
      new_filename = new_filename.strip()
    elif line.startswith('Property changes on:'):
      _, temp_filename = line.split(':', 1)
      # When a file is modified, paths use '/' between directories, however
      # when a property is modified '\' is used on Windows.  Make them the same
      # otherwise the file shows up twice.
      temp_filename = temp_filename.strip().replace('\\', '/')
      if temp_filename != filename:
        # File has property changes but no modifications, create a new diff.
        new_filename = temp_filename
    if new_filename:
      if filename and diff:
        patches.append((filename, ''.join(diff)))
      filename = new_filename
      diff = [line]
      continue
    if diff is not None:
      diff.append(line)
  if filename and diff:
    patches.append((filename, ''.join(diff)))
  return patches
