// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {relativeTime} from
  'elements/chops/chops-timestamp/chops-timestamp-helpers.js';
import {labelRefsToStrings, issueRefsToStrings, componentRefsToStrings,
  userRefsToDisplayNames, statusRefsToStrings} from './converters.js';

export const fieldTypes = Object.freeze({
  APPROVAL_TYPE: 'APPROVAL_TYPE',
  DATE_TYPE: 'DATE_TYPE',
  ENUM_TYPE: 'ENUM_TYPE',
  INT_TYPE: 'INT_TYPE',
  STR_TYPE: 'STR_TYPE',
  USER_TYPE: 'USER_TYPE',
  URL_TYPE: 'URL_TYPE',

  // Frontend types used to handle built in fields like BlockedOn.
  // Although these are not configurable custom field types on the
  // backend, hard-coding these fields types on the frontend allows
  // us to inter-op custom and baked in fields more seamlessly on
  // the frontend.
  ISSUE_TYPE: 'ISSUE_TYPE',
  TIME_TYPE: 'TIME_TYPE',
  COMPONENT_TYPE: 'COMPONENT_TYPE',
  STATUS_TYPE: 'STATUS_TYPE',
  LABEL_TYPE: 'LABEL_TYPE',
  PROJECT_TYPE: 'PROJECT_TYPE',
});

export const EMPTY_FIELD_VALUE = '----';

export function extractTypeForIssue(fieldValues, labelRefs) {
  if (fieldValues) {
    // If there is a custom field for "Type", use that for type.
    const typeFieldValue = fieldValues.find(
      (f) => (f.fieldRef && f.fieldRef.fieldName.toLowerCase() === 'type')
    );
    if (typeFieldValue) {
      return typeFieldValue.value;
    }
  }

  // Otherwise, search through labels for a "Type" label.
  if (labelRefs) {
    const typeLabel = labelRefs.find(
      (l) => l.label.toLowerCase().startsWith('type-'));
    if (typeLabel) {
    // Strip length of prefix.
      return typeLabel.label.substr(5);
    }
  }
  return;
}

// Helper function used for fields with only one value that can be unset.
const wrapValueIfExists = (value) => value ? [value] : [];

// Object containing extraction functions for default fields present in
// Monorail. Each function returns an Array of strings.
// TODO(zhangtiff): Merge this functionality with extract-grid-data.js
// TODO(zhangtiff): Combine this functionality with mr-metadata and
// mr-edit-metadata to allow more expressive representation of built in fields.
const defaultIssueFields = Object.freeze([
  {
    fieldName: 'ID',
    fieldType: fieldTypes.ISSUE_TYPE,
    extractor: ({localId, projectName}) => [{localId, projectName}],
  }, {
    fieldName: 'Project',
    fieldType: fieldTypes.PROJECT_TYPE,
    extractor: (issue) => [issue.projectName],
  }, {
    fieldName: 'Attachments',
    fieldType: fieldTypes.INT_TYPE,
    extractor: (issue) => [issue.attachmentCount || 0],
  }, {
    fieldName: 'AllLabels',
    fieldType: fieldTypes.LABEL_TYPE,
    extractor: (issue) => issue.labelRefs || [],
  }, {
    fieldName: 'Blocked',
    fieldType: fieldTypes.STR_TYPE,
    extractor: (issue) => {
      if (issue.blockedOnIssueRefs && issue.blockedOnIssueRefs.length) {
        return ['Yes'];
      }
      return ['No'];
    },
  }, {
    fieldName: 'BlockedOn',
    fieldType: fieldTypes.ISSUE_TYPE,
    extractor: (issue) => issue.blockedOnIssueRefs || [],
  }, {
    fieldName: 'Blocking',
    fieldType: fieldTypes.ISSUE_TYPE,
    extractor: (issue) => issue.blockingIssueRefs || [],
  }, {
    fieldName: 'CC',
    fieldType: fieldTypes.USER_TYPE,
    extractor: (issue) => issue.ccRefs || [],
  }, {
    fieldName: 'Closed',
    fieldType: fieldTypes.TIME_TYPE,
    extractor: (issue) => wrapValueIfExists(issue.closedTimestamp),
  }, {
    fieldName: 'Component',
    fieldType: fieldTypes.COMPONENT_TYPE,
    extractor: (issue) => issue.componentRefs || [],
  }, { // TODO(zhangtiff): Add "ComponentModified" to v2 API.
    fieldName: 'ComponentModified',
    fieldType: fieldTypes.TIME_TYPE,
    extractor: (issue) => [],
  }, {
    fieldName: 'MergedInto',
    fieldType: fieldTypes.ISSUE_TYPE,
    extractor: (issue) => wrapValueIfExists(issue.mergedInto),
  }, {
    fieldName: 'Modified',
    fieldType: fieldTypes.TIME_TYPE,
    extractor: (issue) => wrapValueIfExists(issue.modifiedTimestamp),
  }, {
    fieldName: 'Reporter',
    fieldType: fieldTypes.USER_TYPE,
    extractor: (issue) => [issue.reporterRef],
  }, {
    fieldName: 'Stars',
    fieldType: fieldTypes.INT_TYPE,
    extractor: (issue) => [issue.starCount || 0],
  }, {
    fieldName: 'Status',
    fieldType: fieldTypes.STATUS_TYPE,
    extractor: (issue) => wrapValueIfExists(issue.statusRef),
  }, { // TODO(zhangtiff): Add "StatusModified" to v2 API.
    fieldName: 'StatusModified',
    fieldType: fieldTypes.TIME_TYPE,
    extractor: (issue) => [],
  }, {
    fieldName: 'Summary',
    fieldType: fieldTypes.STR_TYPE,
    extractor: (issue) => [issue.summary],
  }, {
    fieldName: 'Type',
    fieldType: fieldTypes.ENUM_TYPE,
    extractor: (issue) => wrapValueIfExists(extractTypeForIssue(
      issue.fieldValues, issue.labelRefs)),
  }, {
    fieldName: 'Owner',
    fieldType: fieldTypes.USER_TYPE,
    extractor: (issue) => wrapValueIfExists(issue.ownerRef),
  }, {
    fieldName: 'Opened',
    fieldType: fieldTypes.TIME_TYPE,
    extractor: (issue) => [issue.openedTimestamp],
  },
]);

const defaultIssueFieldMap = new Map();

defaultIssueFields.forEach((field) => {
  defaultIssueFieldMap.set(field.fieldName.toLowerCase(), field);
});

// TODO(zhangtiff): Integrate this logic with Redux selectors somehow.
export const stringValuesForIssueField = (issue, fieldName, projectName) => {
  const key = fieldName.toLowerCase();
  if (defaultIssueFieldMap.has(key)) {
    const bakedFieldDef = defaultIssueFieldMap.get(key);
    const values = bakedFieldDef.extractor(issue);
    switch (bakedFieldDef.fieldType) {
      case fieldTypes.ISSUE_TYPE:
        return issueRefsToStrings(values, projectName);
      case fieldTypes.COMPONENT_TYPE:
        return componentRefsToStrings(values);
      case fieldTypes.LABEL_TYPE:
        return labelRefsToStrings(values);
      case fieldTypes.USER_TYPE:
        return userRefsToDisplayNames(values);
      case fieldTypes.STATUS_TYPE:
        return statusRefsToStrings(values);
      case fieldTypes.TIME_TYPE:
        // TODO(zhangtiff): Find a way to dynamically update displayed
        // time without page reloads.
        return values.map((time) => relativeTime(new Date(time * 1000)));
    }
    return values.map((value) => `${value}`);
  }

  // TODO(zhangtiff): Handle custom fields and label options.

  return [];
};

export const getTypeForFieldName = (fieldName) => {
  const key = fieldName.toLowerCase();

  // If the field is a built in field.
  if (defaultIssueFieldMap.has(key)) {
    return defaultIssueFieldMap.get(key);
  }

  // TODO(zhangtiff): Add type retrieval for custom fields and label options.

  return;
};

// TODO(zhangtiff): Implement hotlist specific fields: Rank, Added, Adder.
