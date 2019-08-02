// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {EMPTY_FIELD_VALUE,
  stringValuesForIssueField} from 'elements/shared/issue-fields.js';
import {getTypeForFieldName, fieldTypes} from '../../shared/issue-fields';


const DEFAULT_HEADER_VALUE = 'All';

// A list of the valid default field names available in an issue grid.
// High cardinality fields must be excluded, so the grid only includes a subset
// of AVAILABLE FIELDS.
export const DEFAULT_GRID_FIELD_NAMES = [
  'Project',
  'Attachments',
  'Blocked',
  'BlockedOn',
  'Blocking',
  'Component',
  'MergedInto',
  'Reporter',
  'Stars',
  'Status',
  'Type',
  'Owner',
];

const SORTABLE_FIELD_TYPES = new Set([
  fieldTypes.DATE_TYPE,
  fieldTypes.ENUM_TYPE,
  fieldTypes.USER_TYPE,
]);

// TODO(zhangtiff): add label options to this.
export const getGridFieldSet = (fieldDefs = []) => {
  const set = new Set(DEFAULT_GRID_FIELD_NAMES);
  fieldDefs.forEach((fd) => {
    if (SORTABLE_FIELD_TYPES.has(fd.fieldRef.type)) {
      set.add(fd.fieldRef.fieldName);
    }
  });
  return set;
};

export const getAvailableGridFields = (fieldDefs = []) => {
  const list = [...getGridFieldSet(fieldDefs)];
  list.sort();

  list.unshift('None');
  return list;
};

// Sort headings functions
// TODO(zhangtiff): Find some way to restructure this code to allow
// sorting functions to sort with raw types instead of stringified values.
function countSort(headings) {
  headings.sort(function(headerA, headerB) {
    return parseInt(headerA) - parseInt(headerB);
  });
  return headings;
}

function issueRefStringSort(headings) {
  headings.sort(function(headerA, headerB) {
    const issueRefA = headerA.split(':');
    const issueRefB = headerB.split(':');
    if (issueRefA[0] != issueRefB[0]) {
      return headerA.localeCompare(headerB);
    } else {
      return parseInt(issueRefA[1]) - parseInt(issueRefB[1]);
    }
  });
  return headings;
}

// TODO(juliacordero): handle sorting ad hoc values
function sortHeadings(headingsSet, attribute) {
  // Track whether EMPTY_FIELD_VALUE is present, and ensure that
  // it is sorted to the first position even for custom fields
  const noHeaderValueIsFound = headingsSet.delete(EMPTY_FIELD_VALUE);
  let headingsList = [...headingsSet];
  let sorter;

  if (headingsSet.has(attribute)) {
    type = getTypeForFieldName(attribute);
    if (type === fieldTypes.ISSUE_TYPE) {
      sorter = issueRefStringSort;
    } else if (type === fieldTypes.INT_TYPE) {
      sorter = countSort;
    }
  }

  if (sorter) {
    headingsList = sorter(headingsList);
  } else {
    headingsList.sort();
  }

  if (noHeaderValueIsFound) {
    headingsList.push(EMPTY_FIELD_VALUE);
  }
  return headingsList;
}

function addValuesToHeadings(headingsSet, valuesAdded) {
  if (!valuesAdded.length) {
    headingsSet.add(EMPTY_FIELD_VALUE);
  }
  for (const value of valuesAdded) {
    headingsSet.add(value);
  }
}

export function makeGridCellKey(x, y) {
  // Note: Some possible x and y values contain ':', '-', and other
  // non-word characters making delimiter options limited.
  return x + ' + ' + y;
}

// Outer function that runs each custom extractor function
export function extractGridData(issues, xField, yField) {
  const gridData = {
    xHeadings: [],
    yHeadings: [],
    sortedIssues: new Map(),
  };

  // TODO(zhangtiff): Make a case insenstitive version of the grid fields.
  const gridFields = new Set();
  getGridFieldSet().forEach((field) => {
    gridFields.add(field.toLowerCase());
  });

  const xHeadingsSet = new Set();
  const yHeadingsSet = new Set();

  const hasX = gridFields.has(xField.toLowerCase());
  const hasY = gridFields.has(yField.toLowerCase());

  let xKeysAdded = [];
  let yKeysAdded = [];

  if (!hasX) {
    xHeadingsSet.add(DEFAULT_HEADER_VALUE);
    xKeysAdded.push(DEFAULT_HEADER_VALUE);
  }

  if (!hasY) {
    yHeadingsSet.add(DEFAULT_HEADER_VALUE);
    yKeysAdded.push(DEFAULT_HEADER_VALUE);
  }

  for (const issue of issues) {
    if (hasX) {
      xKeysAdded = stringValuesForIssueField(issue, xField);
      addValuesToHeadings(xHeadingsSet, xKeysAdded);
    }

    if (hasY) {
      yKeysAdded = stringValuesForIssueField(issue, yField);
      addValuesToHeadings(yHeadingsSet, yKeysAdded);
    }

    // Find every combo of 'xKey yKey' that the issue belongs to
    // and sort it into that cell
    for (const xKey of xKeysAdded) {
      for (const yKey of yKeysAdded) {
        const cellKey = makeGridCellKey(xKey, yKey);
        if (gridData.sortedIssues.has(cellKey)) {
          const cellValue = gridData.sortedIssues.get(cellKey);
          cellValue.push(issue);
          gridData.sortedIssues.set(cellKey, cellValue);
        } else {
          gridData.sortedIssues.set(cellKey, [issue]);
        }
      }
    }
  }

  gridData.xHeadings = sortHeadings(xHeadingsSet, xField);
  gridData.yHeadings = sortHeadings(yHeadingsSet, yField);

  return gridData;
}
