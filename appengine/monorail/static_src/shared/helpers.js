// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import qs from 'qs';


// With lists a and b, get the elements that are in a but not in b.
// result = a - b
export function arrayDifference(listA, listB, equals) {
  if (!equals) {
    equals = (a, b) => (a === b);
  }
  listA = listA || [];
  listB = listB || [];
  return listA.filter((a) => {
    return !listB.find((b) => (equals(a, b)));
  });
}

// Check if a string has a prefix, ignoring case.
export function hasPrefix(str, prefix) {
  return str.toLowerCase().startsWith(prefix.toLowerCase());
}

export function removePrefix(str, prefix) {
  return str.substr(prefix.length);
}

// TODO(zhangtiff): Make this more grammatically correct for
// more than two items.
export function arrayToEnglish(arr) {
  if (!arr) return '';
  return arr.join(' and ');
}

export function pluralize(count, singular, pluralArg) {
  const plural = pluralArg || singular + 's';
  return count === 1 ? singular : plural;
}

export function objectToMap(obj = {}) {
  const map = new Map();
  Object.keys(obj).forEach((key) => {
    map.set(key, obj[key]);
  });
  return map;
}

export function isEmptyObject(obj) {
  return Object.keys(obj).length === 0;
}

export function equalsIgnoreCase(a, b) {
  if (a == b) return true;
  if (!a || !b) return false;
  return a.toLowerCase() === b.toLowerCase();
}

export function immutableSplice(arr, index, count, ...addedItems) {
  if (!arr) return '';

  return [...arr.slice(0, index), ...addedItems, ...arr.slice(index + count)];
}

/**
 * Computes a new URL for a page based on an exiting path and set of query
 * params.
 *
 * @param {String} baseUrl the base URL without query params.
 * @param {Object} oldParams original query params before changes.
 * @param {Object} newParams query parameters to override existing ones.
 * @param {Array} deletedParams list of keys to be cleared.
 * @return {String} the new URL with the updated params.
 */
export function urlWithNewParams(baseUrl = '',
    oldParams = {}, newParams = {}, deletedParams = []) {
  const params = {...oldParams, ...newParams};
  deletedParams.forEach((name) => {
    delete params[name];
  });

  const queryString = qs.stringify(params);

  return `${baseUrl}${queryString ? '?' : ''}${queryString}`;
}

/**
 * Finds out whether a user is a member of a given project based on
 * project membership info.
 *
 * @param {Object} userRef reference to a given user. Expects an id.
 * @param {String} projectName name of the project being searched for.
 * @param {Map} usersProjects all known user project memberships where
 *  keys are userId and values are Objects with expected values
 *  for {ownerOf, memberOf, contributorTo}.
 * @return {Boolean} whether the user is a member of the project or not.
 */
// TODO(crbug.com/monorail/5968): Find a better place for this function to live.
export function userIsMember(userRef, projectName, usersProjects = new Map()) {
  if (!userRef || !userRef.userId || !projectName) return false;
  const userProjects = usersProjects.get(userRef.userId);
  if (!userProjects) return false;
  const {ownerOf = [], memberOf = [], contributorTo = []} = userProjects;
  return ownerOf.includes(projectName) ||
    memberOf.includes(projectName) ||
    contributorTo.includes(projectName);
}
