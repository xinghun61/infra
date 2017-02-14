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
 * @param {string} token security token.
 */
function TKR_checkFieldNameOnServer(projectName, fieldName, token) {
  var url = ('/p/' + projectName + '/fields/checkName' +
             '?field=' + encodeURIComponent(fieldName) +
             '&token=' + token);
  TKR_fieldNameXmlHttp = XH_XmlHttpCreate();
  XH_XmlHttpGET(TKR_fieldNameXmlHttp, url, TKR_fieldNameCallback);
}

/**
 * The communication with the server has made some progress.  If it is
 * done, then process the response.
 */
function TKR_fieldNameCallback() {
  if (TKR_fieldNameXmlHttp.readyState == 4) {
    if (TKR_fieldNameXmlHttp.status == 200) {
      TKR_gotFieldNameFeed(TKR_fieldNameXmlHttp);
    }
  }
}


/**
 * Function that evaluates the server response and sets the error message.
 * @param {object} xhr AJAX response with JSON text.
 */
function TKR_gotFieldNameFeed(xhr) {
  var json_data = null;
  try {
    json_data = CS_parseJSON(xhr);
  }
  catch (e) {
    return;
  }
  var errorMessage = json_data['error_message'];
  $('fieldnamefeedback').textContent = errorMessage;

  var choicesLines = [];
  if (json_data['choices'].length > 0) {
    for (var i = 0; i < json_data['choices'].length; i++) {
      choicesLines.push(
          json_data['choices'][i]['name'] + ' = ' +
          json_data['choices'][i]['doc']);
    }
    $('choices').textContent = choicesLines.join('\n');
    $('field_type').value = 'enum_type';
    $('choices_row').style.display = '';
    enableOtherTypeOptions(true);
  } else {
    enableOtherTypeOptions(false);
  }

  $('submit_btn').disabled = errorMessage ? 'disabled' : '';
}


function enableOtherTypeOptions(disabled) {
  var type_option_el = $('field_type').firstChild;
  while (type_option_el) {
    if (type_option_el.tagName == 'OPTION') {
      if (type_option_el.value != 'enum_type') {
        type_option_el.disabled = disabled ? 'disabled' : '';
      }
    }
    type_option_el = type_option_el.nextSibling;
  }
}
