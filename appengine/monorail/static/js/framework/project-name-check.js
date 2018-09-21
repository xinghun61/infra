/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview Functions that support project name checks when
 * creating a new project.
 */

/**
 * Function that communicates with the server.
 * @param {string} projectName The proposed project name.
 */
async function checkProjectName(projectName) {
  const message = {
    project_name: projectName
  };
  const response = await window.prpcClient.call(
      'monorail.Projects', 'CheckProjectName', message);
  if (response.error) {
    $('projectnamefeedback').textContent = response.error;
    $('submit_btn').disabled = 'disabled';
  }
}

// Make this function globally available
_CP_checkProjectName = checkProjectName;
