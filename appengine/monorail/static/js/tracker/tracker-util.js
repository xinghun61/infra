/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS utilities used by other JS files in Monorail.
 */


/**
 * Add an indexOf method to all arrays, if this brower's JS implementation
 * does not already have it.
 * @param {Object} item The item to find
 * @return {number} The index of the given item, or -1 if not found.
 */
if (Array.prototype.indexOf == undefined) {
  Array.prototype.indexOf = function(item) {
    for (let i = 0; i < this.length; ++i) {
      if (this[i] == item) return i;
    }
    return -1;
  };
}


/**
 * This function works around a FF HTML layout problem.  The table
 * width is somehow rendered at 100% when the table contains a
 * display:none element, later, when that element is displayed, the
 * table renders at the correct width.  The work-around is to have the
 * element initiallye displayed so that the table renders properly,
 * but then immediately hide the element until it is needed.
 *
 * TODO(jrobbins): Find HTML markup that FF can render more
 * consistently.  After that, I can remove this hack.
 */
function TKR_forceProperTableWidth() {
  let e = $('confirmarea');
  if (e) e.style.display='none';
}


function TKR_parseIssueRef(issueRef) {
  issueRef = issueRef.trim();
  if (!issueRef) {
    return null;
  }

  let projectName = window.CS_env.projectName;
  let localId = issueRef;
  if (issueRef.includes(':')) {
    const parts = issueRef.split(':', 2);
    projectName = parts[0];
    localId = parts[1];
  }

  return {
    project_name: projectName,
    local_id: localId};
}


function _buildFieldsForIssueDelta(issueDelta, valuesByName) {
  issueDelta.field_vals_add = [];
  issueDelta.field_vals_remove = [];
  issueDelta.fields_clear = [];

  valuesByName.forEach((values, key, map) => {
    if (key.startsWith('op_custom_') && values == 'clear') {
      const field_id = key.substring('op_custom_'.length);
      issueDelta.fields_clear.push({field_id: field_id});
    } else if (key.startsWith('custom_')) {
      const field_id = key.substring('custom_'.length);
      values = values.filter(Boolean);
      if (valuesByName.get('op_' + key) === 'remove') {
        values.forEach((value) => {
          issueDelta.field_vals_remove.push({
            field_ref: {field_id: field_id},
            value: value});
        });
      } else {
        values.forEach((value) => {
          issueDelta.field_vals_add.push({
            field_ref: {field_id: field_id},
            value: value});
        });
      }
    }
  });
}


function _classifyPlusMinusItems(values) {
  let result = {
    add: [],
    remove: []};
  values = new Set(values);
  values.forEach((value) => {
    if (!value.startsWith('-') && value) {
      result.add.push(value);
    } else if (value.startsWith('-') && value.substring(1)) {
      result.remove.push(value);
    }
  });
  return result;
}


function TKR_buildIssueDelta(valuesByName) {
  let issueDelta = {};

  if (valuesByName.has('status')) {
    issueDelta.status = valuesByName.get('status')[0];
  }
  if (valuesByName.has('owner')) {
    issueDelta.owner_ref = {
      display_name: valuesByName.get('owner')[0].trim().toLowerCase()};
  }
  if (valuesByName.has('cc')) {
    const cc_usernames = _classifyPlusMinusItems(
      valuesByName.get('cc')[0].toLowerCase().split(/[,;\s]+/));
    issueDelta.cc_refs_add = cc_usernames.add.map(
      (email) => ({display_name: email}));
    issueDelta.cc_refs_remove = cc_usernames.remove.map(
      (email) => ({display_name: email}));
  }
  if (valuesByName.has('components')) {
    const components = _classifyPlusMinusItems(
      valuesByName.get('components')[0].split(/[,;\s]/));
    issueDelta.comp_refs_add = components.add.map(
      (path) => ({path: path}));
    issueDelta.comp_refs_remove = components.remove.map(
      (path) => ({path: path}));
  }
  if (valuesByName.has('label')) {
    const labels = _classifyPlusMinusItems(valuesByName.get('label'));
    issueDelta.label_refs_add = labels.add.map(
      (label) => ({label: label}));
    issueDelta.label_refs_remove = labels.remove.map(
      (label) => ({label: label}));
  }
  if (valuesByName.has('blocked_on')) {
    const blockedOn = _classifyPlusMinusItems(valuesByName.get('blocked_on'));
    issueDelta.blocked_on_refs_add = blockedOn.add.map(TKR_parseIssueRef);
    issueDelta.blocked_on_refs_add = blockedOn.remove.map(TKR_parseIssueRef);
  }
  if (valuesByName.has('blocking')) {
    const blocking = _classifyPlusMinusItems(valuesByName.get('blocking'));
    issueDelta.blocking_refs_add = blocking.add.map(TKR_parseIssueRef);
    issueDelta.blocking_refs_add = blocking.remove.map(TKR_parseIssueRef);
  }
  if (valuesByName.has('merge_into')) {
    issueDelta.merged_into_ref = TKR_parseIssueRef(
      valuesByName.get('merge_into')[0]);
  }
  if (valuesByName.has('summary')) {
    issueDelta.summary = valuesByName.get('summary')[0];
  }

  _buildFieldsForIssueDelta(issueDelta, valuesByName);

  return issueDelta;
}
