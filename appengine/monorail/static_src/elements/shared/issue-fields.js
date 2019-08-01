// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

export const fieldTypes = Object.freeze({
  APPROVAL_TYPE: 'APPROVAL_TYPE',
  DATE_TYPE: 'DATE_TYPE',
  ENUM_TYPE: 'ENUM_TYPE',
  INT_TYPE: 'INT_TYPE',
  STR_TYPE: 'STR_TYPE',
  USER_TYPE: 'USER_TYPE',
  URL_TYPE: 'URL_TYPE',
});

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
