# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Presubmit script for Chromium Infra JS resources."""

import os
import subprocess

def RunNode(infra_root, cmd_parts, stdout=None):
  """Runs node from CIPD package under infra repo."""
  # Gets the node path from CIPD which is setup when infra repo is
  # checked out.
  cipd_node = os.path.join(infra_root, 'cipd', 'bin', 'node')
  process = subprocess.Popen(
      [cipd_node] + cmd_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  stdout, stderr = process.communicate()

  if stderr:
    raise RuntimeError('%s failed: %s' % (
        ' '.join([cipd_node] + cmd_parts), stderr))

  return stdout


def NPMInstall(infra_root):
  """Runs node and install packages."""
  cipd_npm = os.path.join(
      infra_root, 'cipd', 'lib', 'node_modules', 'npm', 'bin', 'npm-cli.js')
  return RunNode(infra_root, [cipd_npm, 'install'])


class JSChecker(object):

  def __init__(self, input_api, output_api, file_filter=None):
    self.input_api = input_api
    self.output_api = output_api
    self.file_filter = file_filter

  def _PathInNodeModules(self, *args):
    """Returns the path of the executable in node module."""
    node_module = self.input_api.os_path.join(
        self.input_api.PresubmitLocalPath(), 'node_modules')
    return self.input_api.os_path.join(node_module, *args)

  def RunESLint(self, args=None):
    infra_root = self.input_api.os_path.dirname(
        self.input_api.PresubmitLocalPath())
    eslint_path = self._PathInNodeModules('eslint', 'bin', 'eslint')

    NPMInstall(infra_root)
    # Runs ESLint on modified files.
    return RunNode(infra_root, [eslint_path] + args)

  def RunESLintChecks(
      self, affected_js_files, style='unix', only_changed_lines=True):
    """Runs lint checks using ESLint.

    The ESLint rules being applied are defined in the
    .eslintrc.json configuration file.
    """
    # Extract paths to be passed to ESLint.
    affected_js_files_paths = []
    presubmit_path = self.input_api.PresubmitLocalPath()
    changed_lines = []
    for f in affected_js_files:
      affected_js_files_paths.append(
          self.input_api.os_path.relpath(f.AbsoluteLocalPath(), presubmit_path))
      changed_lines.extend(self.GetChangedLines(f))
    args = ['--no-color', '--format', style,
            '--ignore-pattern', '\'!.eslintrc.json\'']
    args += affected_js_files_paths
    output = self.RunESLint(args=args)
    if only_changed_lines:
      # Filter ESList errors for only modified lines.
      output = self.FilterESLintForChangedLines(output, changed_lines)
    if not output:
      return []
    output = 'ESLint (%s files)\n%s' % (len(affected_js_files_paths), output)
    return [self.output_api.PresubmitPromptWarning(output)]

  def GetChangedLines(self, affect_file_obj):
    """Gets a list of string to filter from ESLint output.

    This list contains string in the format of <filename>:<line_number>
    and is matched with ESList output to filter errors.
    """
    absolute_path = affect_file_obj.AbsoluteLocalPath()
    return ['%s:%s' % (absolute_path, line[0])
            for line in affect_file_obj.ChangedContents()]

  def FilterESLintForChangedLines(self, es_output, lines_to_filter):
    """Returned the filtered errors for changed lines."""
    filter_output = [es_line for es_line in es_output.split('\n') if any(
                     line in es_line for line in lines_to_filter)]
    return '\n'.join(filter_output)

  def RunChecks(self):
    """Checks for violations of the JavaScript style guide.

    See https://goo.gl/Ld1CqR.
    """
    results = []

    affected_files = self.input_api.AffectedFiles(
        file_filter=self.file_filter, include_deletes=False)
    affected_js_files = filter(
        lambda f: f.LocalPath().endswith('.js'), affected_files)

    if affected_js_files:
      self.input_api.logging.info(
          'Running appengine eslint on %d JS file(s)', len(affected_js_files))
      results += self.RunESLintChecks(affected_js_files)


    if results:
      results.append(self.output_api.PresubmitNotifyResult(
          'See the JavaScript style guide at https://goo.gl/Ld1CqR.'))

    return results
