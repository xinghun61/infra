/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS code for editing fields and field definitions.
 */

var TKR_fieldNameXmlHttp;


/**
 * Function that communicates with the server.
 * @param {string} projectName Current project name.
 * @param {string} fieldName The proposed field name.
 */
async function TKR_checkFieldNameOnServer(projectName, fieldName) {
  fieldName = fieldName.toLowerCase();

  const fieldNameMessage = {
    project_name: projectName,
    field_name: fieldName,
  };
  const labelOptionsMessage = {
    project_name: projectName,
  };
  const responses = await Promise.all([
      window.prpcClient.call(
          'monorail.Projects', 'CheckFieldName', fieldNameMessage),
      window.prpcClient.call(
          'monorail.Projects', 'GetLabelOptions', labelOptionsMessage),
  ]);

  const fieldNameResponse = responses[0];
  const labelsResponse = responses[1];

  $('fieldnamefeedback').textContent = fieldNameResponse.error || '';
  $('submit_btn').disabled = fieldNameResponse.error ? 'disabled' : '';

  const maskedLabels = (labelsResponse.labelOptions || []).filter(
      label_def => label_def.label.toLowerCase().startsWith(fieldName + '-'));

  if (maskedLabels.length === 0) {
    enableOtherTypeOptions(false);
  } else {
    const prefixLength = fieldName.length + 1;
    const padLength = Math.max.apply(null, maskedLabels.map(
        label_def => label_def.label.length - prefixLength));
    const choicesLines = maskedLabels.map(label_def => {
      // Strip the field name from the label.
      const choice = label_def.label.substr(prefixLength);
      return choice.padEnd(padLength) + ' = ' + label_def.docstring;
    });
    $('choices').textContent = choicesLines.join('\n');
    $('field_type').value = 'enum_type';
    $('choices_row').style.display = '';
    enableOtherTypeOptions(true);
  }
}


function enableOtherTypeOptions(disabled) {
  let type_option_el = $('field_type').firstChild;
  while (type_option_el) {
    if (type_option_el.tagName == 'OPTION') {
      if (type_option_el.value != 'enum_type') {
        type_option_el.disabled = disabled ? 'disabled' : '';
      }
    }
    type_option_el = type_option_el.nextSibling;
  }
}
