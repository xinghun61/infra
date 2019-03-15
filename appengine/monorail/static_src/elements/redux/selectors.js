// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {fieldTypes} from '../shared/field-types.js';
import {createSelector} from 'reselect';

// TODO(zhangtiff): Eventually Monorail's Redux state will store
// multiple issues, and this selector will have to find the viewed
// issue based on a viewed issue ref.
const viewedIssue = (state) => state.issue;
const projectConfig = (state) => state.projectConfig;
const fieldDefs = createSelector(
  projectConfig,
  (config) => config && config.fieldDefs
);
const issueFieldValues = createSelector(
  viewedIssue,
  (issue) => issue && issue.fieldValues
);
const issueType = createSelector(
  issueFieldValues,
  (fieldValues) => {
    if (!fieldValues) return;
    const typeFieldValue = fieldValues.find(
      (f) => (f.fieldRef && f.fieldRef.fieldName === 'Type')
    );
    if (typeFieldValue) {
      return typeFieldValue.value;
    }
    return;
  }
);
const issueIsOpen = createSelector(
  viewedIssue,
  (issue) => issue && issue.statusRef && issue.statusRef.meansOpen
);
// values (from issue.fieldValues) is an array with one entry per value.
// We want to turn this into a map of fieldNames -> values.
const issueFieldValueMap = createSelector(
  issueFieldValues,
  (fieldValues) => {
    if (!fieldValues) return new Map();
    const acc = new Map();
    for (const v of fieldValues) {
      if (!v || !v.fieldRef || !v.fieldRef.fieldName || !v.value) continue;
      let key = [v.fieldRef.fieldName];
      if (v.phaseRef && v.phaseRef.phaseName) {
        key.push(v.phaseRef.phaseName);
      }
      key = key.join(' ');
      if (acc.has(key)) {
        acc.get(key).push(v.value);
      } else {
        acc.set(key, [v.value]);
      }
    }
    return acc;
  }
);
// Look up components by path.
const componentsMap = createSelector(
  projectConfig,
  (config) => {
    if (!config || !config.componentDefs) return new Map();
    const acc = new Map();
    for (const v of config.componentDefs) {
      let key = v.path;
      acc.set(key, v);
    }
    return acc;
  }
);
// Get the list of full componentDefs for the viewed issue.
const componentsForIssue = createSelector(
  viewedIssue,
  componentsMap,
  (issue, components) => {
    if (!issue || !issue.componentRefs) return [];
    return issue.componentRefs.map((comp) => components.get(comp.path));
  }
);
const fieldDefsForIssue = createSelector(
  fieldDefs,
  issueType,
  (fieldDefs, issueType) => {
    if (!fieldDefs) return [];
    issueType = issueType || '';
    return fieldDefs.filter((f) => {
      // Skip approval type and phase fields here.
      if (f.fieldRef.approvalName
          || f.fieldRef.type === fieldTypes.APPROVAL_TYPE
          || f.isPhaseField) {
        return false;
      }

      // If this fieldDef belongs to only one type, filter out the field if
      // that type isn't the specified issueType.
      if (f.applicableType && issueType.toLowerCase()
          !== f.applicableType.toLowerCase()) {
        return false;
      }

      return true;
    });
  }
);
const fieldDefsForPhases = createSelector(
  fieldDefs,
  (fieldDefs) => {
    if (!fieldDefs) return [];
    return fieldDefs.filter((f) => f.isPhaseField);
  }
);
const fieldDefsByApprovalName = createSelector(
  fieldDefs,
  (fieldDefs) => {
    if (!fieldDefs) return new Map();
    const acc = new Map();
    for (const fd of fieldDefs) {
      if (fd.fieldRef && fd.fieldRef.approvalName) {
        if (acc.has(fd.fieldRef.approvalName)) {
          acc.get(fd.fieldRef.approvalName).push(fd);
        } else {
          acc.set(fd.fieldRef.approvalName, [fd]);
        }
      }
    }
    return acc;
  }
);

export const selectors = Object.freeze({
  viewedIssue,
  projectConfig,
  fieldDefs,
  issueFieldValues,
  issueType,
  issueIsOpen,
  issueFieldValueMap,
  componentsMap,
  componentsForIssue,
  fieldDefsForIssue,
  fieldDefsForPhases,
  fieldDefsByApprovalName,
});
