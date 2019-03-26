// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {createSelector} from 'reselect';
import {fieldTypes} from '../shared/field-types.js';
import {removePrefix} from '../shared/helpers.js';
import {issueRefToString} from '../shared/converters.js';
import * as project from './project.js';

// Actions

/* State Shape
*/

// Reducers

// Selectors
const RESTRICT_VIEW_PREFIX = 'restrict-view-';
const RESTRICT_EDIT_PREFIX = 'restrict-editissue-';
const RESTRICT_COMMENT_PREFIX = 'restrict-addissuecomment-';

// TODO(zhangtiff): Eventually Monorail's Redux state will store
// multiple issues, and this selector will have to find the viewed
// issue based on a viewed issue ref.
export const issue = (state) => state.issue;

export const fieldValues = createSelector(
  issue,
  (issue) => issue && issue.fieldValues
);

export const type = createSelector(
  fieldValues,
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

export const restrictions = createSelector(
  issue,
  (issue) => {
    if (!issue || !issue.labelRefs) return {};

    const restrictions = {};

    issue.labelRefs.forEach((labelRef) => {
      const label = labelRef.label;
      const lowerCaseLabel = label.toLowerCase();

      if (lowerCaseLabel.startsWith(RESTRICT_VIEW_PREFIX)) {
        const permissionType = removePrefix(label, RESTRICT_VIEW_PREFIX);
        if (!('view' in restrictions)) {
          restrictions['view'] = [permissionType];
        } else {
          restrictions['view'].push(permissionType);
        }
      } else if (lowerCaseLabel.startsWith(RESTRICT_EDIT_PREFIX)) {
        const permissionType = removePrefix(label, RESTRICT_EDIT_PREFIX);
        if (!('edit' in restrictions)) {
          restrictions['edit'] = [permissionType];
        } else {
          restrictions['edit'].push(permissionType);
        }
      } else if (lowerCaseLabel.startsWith(RESTRICT_COMMENT_PREFIX)) {
        const permissionType = removePrefix(label, RESTRICT_COMMENT_PREFIX);
        if (!('comment' in restrictions)) {
          restrictions['comment'] = [permissionType];
        } else {
          restrictions['comment'].push(permissionType);
        }
      }
    });

    return restrictions;
  }
);

export const isRestricted = createSelector(
  restrictions,
  (restrictions) => {
    if (!restrictions) return false;
    return ('view' in restrictions && !!restrictions['view'].length) ||
      ('edit' in restrictions && !!restrictions['edit'].length) ||
      ('comment' in restrictions && !!restrictions['comment'].length);
  }
);

export const isOpen = createSelector(
  issue,
  (issue) => issue && issue.statusRef && issue.statusRef.meansOpen || false
);

const blockingIssueRefs = createSelector(
  issue,
  (issue) => issue && issue.blockingIssueRefs || []
);

const blockedOnIssueRefs = createSelector(
  issue,
  (issue) => issue && issue.blockedOnIssueRefs || []
);

export const relatedIssues = (state) => state.relatedIssues;

export const blockingIssues = createSelector(
  blockingIssueRefs, relatedIssues,
  (blockingRefs, relatedIssues) => blockingRefs.map((ref) => {
    const key = issueRefToString(ref);
    if (relatedIssues.has(key)) {
      return relatedIssues.get(key);
    }
    return ref;
  })
);

export const blockedOnIssues = createSelector(
  blockedOnIssueRefs, relatedIssues,
  (blockedOnRefs, relatedIssues) => blockedOnRefs.map((ref) => {
    const key = issueRefToString(ref);
    if (relatedIssues.has(key)) {
      return relatedIssues.get(key);
    }
    return ref;
  })
);

export const mergedInto = createSelector(
  issue, relatedIssues,
  (issue, relatedIssues) => issue && issue.mergedIntoRef
    && relatedIssues.get(issueRefToString(issue.mergedIntoRef))
);

export const sortedBlockedOn = createSelector(
  blockedOnIssues,
  (blockedOn) => blockedOn.sort((a, b) => {
    const aIsOpen = a.statusRef && a.statusRef.meansOpen ? 1 : 0;
    const bIsOpen = b.statusRef && b.statusRef.meansOpen ? 1 : 0;
    return bIsOpen - aIsOpen;
  })
);

// values (from issue.fieldValues) is an array with one entry per value.
// We want to turn this into a map of fieldNames -> values.
export const fieldValueMap = createSelector(
  fieldValues,
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

// Get the list of full componentDefs for the viewed issue.
export const components = createSelector(
  issue,
  project.componentsMap,
  (issue, components) => {
    if (!issue || !issue.componentRefs) return [];
    return issue.componentRefs.map((comp) => components.get(comp.path));
  }
);

export const fieldDefs = createSelector(
  project.fieldDefs,
  type,
  (fieldDefs, type) => {
    if (!fieldDefs) return [];
    type = type || '';
    return fieldDefs.filter((f) => {
      // Skip approval type and phase fields here.
      if (f.fieldRef.approvalName
          || f.fieldRef.type === fieldTypes.APPROVAL_TYPE
          || f.isPhaseField) {
        return false;
      }

      // If this fieldDef belongs to only one type, filter out the field if
      // that type isn't the specified type.
      if (f.applicableType && type.toLowerCase()
          !== f.applicableType.toLowerCase()) {
        return false;
      }

      return true;
    });
  }
);

// Action Creators
