// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /(?:([a-z0-9-]+):)?(\d+)/i;

export function displayNameToUserRef(displayName) {
  return {displayName};
}

export function labelStringToRef(label) {
  return {label};
}

export function fieldNameToLabelPrefix(fieldName) {
  return `${fieldName.toLowerCase()}-`;
}

export function componentStringToRef(path) {
  return {path};
}

export function issueStringToRef(defaultProjectName, idStr) {
  const matches = idStr.match(ISSUE_ID_REGEX);
  if (!matches) {
    // TODO(zhangtiff): Add proper clientside form validation.
    throw new Error('Bug has an invalid input format');
  }
  const projectName = matches[1] ? matches[1] : defaultProjectName;
  const localId = Number.parseInt(matches[2]);
  return {localId, projectName};
}

export function issueRefToString(ref, projectName) {
  if (!ref) return '';
  if (projectName && projectName.length &&
      ref.projectName.toLowerCase() === projectName.toLowerCase()) {
    return `${ref.localId}`;
  }
  return `${ref.projectName}:${ref.localId}`;
}
