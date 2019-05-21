// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {equalsIgnoreCase} from './helpers';
import {UserInputError} from 'elements/shared/errors.js';

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /(?:([a-z0-9-]+):)?(\d+)/i;

export function displayNameToUserRef(displayName) {
  return {displayName};
}

export function userRefToDisplayName(userRef) {
  return userRef && userRef.displayName;
}

export function userRefsToDisplayNames(userRefs) {
  if (!userRefs) return [];
  return userRefs.map(userRefToDisplayName);
}

export function userRefsWithIds(userRefs) {
  if (!userRefs) return [];
  return userRefs.filter((u) => u.userId);
}

export function filteredUserDisplayNames(userRefs) {
  if (!userRefs) return [];
  return userRefsToDisplayNames(userRefsWithIds(userRefs));
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

export function componentRefToString(componentRef) {
  return componentRef && componentRef.path;
}

export function componentRefsToStrings(componentRefs) {
  if (!componentRefs) return [];
  return componentRefs.map(componentRefToString);
}

export function issueStringToRef(defaultProjectName, idStr) {
  if (!idStr) return {};

  const matches = idStr.match(ISSUE_ID_REGEX);
  if (!matches) {
    throw new UserInputError('Expected [projectName:]issueId.');
  }
  const projectName = matches[1] ? matches[1] : defaultProjectName;
  const localId = Number.parseInt(matches[2]);
  return {localId, projectName};
}

export function issueRefToString(ref, projectName) {
  if (!ref) return '';
  if (projectName && projectName.length
      && equalsIgnoreCase(ref.projectName, projectName)) {
    return `${ref.localId}`;
  }
  return `${ref.projectName}:${ref.localId}`;
}

export function issueRefsToStrings(arr, projectName) {
  if (!arr || !arr.length) return [];
  return arr.map((ref) => issueRefToString(ref, projectName));
}

export function commentListToDescriptionList(comments) {
  if (!comments) return [];
  // First comment is always a description, even if it doesn't have a
  // descriptionNum.
  return comments.filter((c, i) => !i || c.descriptionNum);
}
