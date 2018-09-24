/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS code for editing components and component definitions.
 */

var TKR_leafNameXmlHttp;

var TKR_leafNameRE = /^[a-zA-Z]([-_]?[a-zA-Z0-9])+$/;
var TKR_oldName = '';

/**
 * Function to validate the component leaf name..
 * @param {string} projectName Current project name.
 * @param {string} parentPath Path to this component's parent.
 * @param {string} originalName Original leaf name, keeping that is always OK.
 * @param {string} token security token.
 */
function TKR_checkLeafName(projectName, parentPath, originalName, token) {
  var name = $('leaf_name').value;
  var feedback = $('leafnamefeedback');
  if (name == originalName) {
    $('submit_btn').disabled = '';
    feedback.textContent = '';
  } else if (name != TKR_oldName) {
    $('submit_btn').disabled = 'disabled';
    if (name == '') {
      feedback.textContent = 'Please choose a name';
    } else if (!TKR_leafNameRE.test(name)) {
      feedback.textContent = 'Invalid component name';
    } else if (name.length > 30) {
      feedback.textContent = 'Name is too long';
    } else {
      TKR_checkLeafNameOnServer(projectName, parentPath, name, token);
    }
  }
  TKR_oldName = name;
}



/**
 * Function that communicates with the server.
 * @param {string} projectName Current project name.
 * @param {string} leafName The proposed leaf name.
 * @param {string} token security token.
 */
async function TKR_checkLeafNameOnServer(projectName, parentPath, leafName) {
  const message = {
    project_name: projectName,
    parent_path: parentPath,
    component_name: leafName
  };
  const response = await window.prpcClient.call(
      'monorail.Projects', 'CheckComponentName', message);

  $('leafnamefeedback').textContent = response.error || '';
  $('submit_btn').disabled = response.error ? 'disabled' : '';
}
