// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import qs from 'qs';

import {equalsIgnoreCase} from './helpers';
import {fromShortlink} from 'elements/shared/federated.js';
import {UserInputError} from 'elements/shared/errors.js';

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /(?:([a-z0-9-]+):)?(\d+)/i;

// RFC 2821-compliant email address regex used by the server when validating
// email addresses.
const RFC_2821_EMAIL_REGEX = /^[-a-zA-Z0-9!#$%&'*+\/=?^_`{|}~]+(?:[.][-a-zA-Z0-9!#$%&'*+\/=?^_`{|}~]+)*@(?:(?:[0-9a-zA-Z](?:[-]*[0-9a-zA-Z]+)*)(?:\.[0-9a-zA-Z](?:[-]*[0-9a-zA-Z]+)*)*)\.(?:[a-zA-Z]{2,9})$/;

export function displayNameToUserRef(displayName) {
  if (displayName && !RFC_2821_EMAIL_REGEX.test(displayName)) {
    throw new UserInputError(
      `Invalid email address: ${displayName}`);
  }
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

export function labelRefToString(labelRef) {
  if (!labelRef) return;
  return labelRef.label;
}

export function labelRefsToStrings(labelRefs) {
  if (!labelRefs) return [];
  return labelRefs.map(labelRefToString);
}

export function fieldNameToLabelPrefix(fieldName) {
  return `${fieldName.toLowerCase()}-`;
}

export function labelNameToLabelPrefix(label) {
  if (!label) return;
  return label.split('-')[0];
}

export function statusRefToString(statusRef) {
  return statusRef.status;
}

export function statusRefsToStrings(statusRefs) {
  return statusRefs.map(statusRefToString);
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

  // If the string includes a slash, it's an external tracker ref.
  if (idStr.includes('/')) {
    return {extIdentifier: idStr};
  }

  const matches = idStr.match(ISSUE_ID_REGEX);
  if (!matches) {
    throw new UserInputError(
      `Invalid issue ref: ${idStr}. Expected [projectName:]issueId.`);
  }
  const projectName = matches[1] ? matches[1] : defaultProjectName;
  const localId = Number.parseInt(matches[2]);
  return {localId, projectName};
}

export function issueStringToBlockingRef(projectName, localId, idStr) {
  const result = issueStringToRef(projectName, idStr);
  if (result.projectName === projectName && result.localId === localId) {
    throw new UserInputError(
      `Invalid issue ref: ${idStr}. Cannot merge or block an issue on itself.`);
  }
  return result;
}

export function issueRefToString(ref, projectName) {
  if (!ref) return '';

  if (ref.hasOwnProperty('extIdentifier')) {
    return ref.extIdentifier;
  }

  if (projectName && projectName.length
      && equalsIgnoreCase(ref.projectName, projectName)) {
    return `${ref.localId}`;
  }
  return `${ref.projectName}:${ref.localId}`;
}

export function issueToIssueRef(issue) {
  if (!issue) return {};

  return {localId: issue.localId,
    projectName: issue.projectName};
}

export function issueRefToUrl(ref, queryParams = {}) {
  if (!ref) return '';

  if (ref.extIdentifier) {
    const extRef = fromShortlink(ref.extIdentifier);
    if (!extRef) {
      console.error(`No tracker found for reference: ${ref.extIdentifier}`);
      return '';
    }
    return extRef.toURL();
  }

  let paramString = '';
  if (Object.keys(queryParams).length) {
    delete queryParams.id;

    paramString = `&${qs.stringify(queryParams)}`;
  }

  return `/p/${ref.projectName}/issues/detail?id=${ref.localId}${paramString}`;
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

export function valueToFieldValue(fieldRef, value) {
  return {fieldRef, value};
}
