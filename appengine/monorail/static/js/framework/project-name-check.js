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
function checkProjectName(projectName) {
  var createProjectUrl = '/hosting/createProject/checkProjectName.do';
  var args = {
    'project': projectName
  };
  CS_doPost(createProjectUrl, nameTaken, args);
}

/**
 * Function that evaluates the server response and sets the error message.
 * @param {event} event with xhr server's JSON response to the AJAX request.
 */
function nameTaken(event) {
  var xhr = event.target;
  if (xhr.readyState != 4 || xhr.status != 200)
    return;
  var resp = CS_parseJSON(xhr);
  var errorMessage = resp['error_message'];
  document.getElementById('projectnamefeedback').textContent = errorMessage;
  if (errorMessage != '') {
    document.getElementById('submit_btn').disabled = 'disabled';
  }
}

// Make this function globally available
_CP_checkProjectName = checkProjectName;
