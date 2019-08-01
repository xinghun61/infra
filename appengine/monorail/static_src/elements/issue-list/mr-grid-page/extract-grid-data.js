// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {extractTypeForIssue, EMPTY_FIELD_VALUE} from
  'elements/shared/issue-fields.js';
import {issueRefToString} from 'elements/shared/converters.js';

const gridHeadings = new Map();
const DEFAULT_HEADER_VALUE = 'All';

// TODO(juliacordero): write functions to extract from custom fields

// TODO(juliacordero): Uncomment once attachmentCount functionality
// is re-enabled
/* Headings.set(
  'Attachments',
  {
    extractor: extractAttachmentsHeadings,
    sorter: countSort,
  }
); */
gridHeadings.set(
  'Blocked',
  {
    extractor: extractBlockedHeadings,
    sorter: null,
  }
);
gridHeadings.set(
  'BlockedOn',
  {
    extractor: extractBlockedOnHeadings,
    sorter: issueRefStringSort,
  }
);
gridHeadings.set(
  'Blocking',
  {
    extractor: extractBlockingHeadings,
    sorter: issueRefStringSort,
  }
);
gridHeadings.set(
  'Component',
  {
    extractor: extractComponentHeadings,
    sorter: null,
  }
);
gridHeadings.set(
  'Reporter',
  {
    extractor: extractReporterHeadings,
    sorter: null,
  }
);
gridHeadings.set(
  'Stars',
  {
    extractor: extractStarsHeadings,
    sorter: countSort,
  }
);
gridHeadings.set(
  'Status',
  {
    extractor: extractStatusHeadings,
    sorter: null,
  }
);
gridHeadings.set(
  'Type',
  {
    extractor: extractTypeHeadings,
    sorter: null,
  }
);

// Extract headings functions
// TODO(juliacordero): Uncomment once attachmentCount functionality
// is re-enabled (bug# 5857)
/* function extractAttachmentsHeadings(issue, keysSet) { // countSort
  keysSet.add(issue.attachmentCount);
  return keysSet;
} */

function extractBlockedHeadings(issue) {
  const keysAdded = [];
  if (issue.blockedOnIssueRefs) {
    keysAdded.push('Yes');
  } else if (!issue.blockedOnIssueRefs) {
    keysAdded.push('No');
  }
  return keysAdded;
}

function extractBlockedOnHeadings(issue) {
  const keysAdded = [];
  if (!issue.blockedOnIssueRefs) {
    keysAdded.push(EMPTY_FIELD_VALUE);
  } else {
    for (const blocked of issue.blockedOnIssueRefs) {
      const issueKey = issueRefToString(blocked, '');
      keysAdded.push(issueKey);
    }
  }
  return keysAdded;
}

function extractBlockingHeadings(issue) {
  const keysAdded = [];
  if (!issue.blockingIssueRefs) {
    keysAdded.push(EMPTY_FIELD_VALUE);
  } else {
    for (const blocking of issue.blockingIssueRefs) {
      const issueKey = issueRefToString(blocking, '');
      keysAdded.push(issueKey);
    }
  }
  return keysAdded;
}

function extractComponentHeadings(issue) {
  const keysAdded = [];
  if (!issue.componentRefs) {
    keysAdded.push(EMPTY_FIELD_VALUE);
  } else {
    for (const component of issue.componentRefs) {
      keysAdded.push(component.path);
    }
  }
  return keysAdded;
}

function extractReporterHeadings(issue) {
  return [issue.reporterRef.displayName];
}

function extractStarsHeadings(issue) {
  return [issue.starCount];
}

function extractStatusHeadings(issue) {
  return [issue.statusRef.status];
}

function extractTypeHeadings(issue) {
  const labelRefs = issue.labelRefs;
  const fieldValues = issue.fieldValues;
  const type = extractTypeForIssue(fieldValues, labelRefs);
  if (type) {
    return [type];
  } else {
    return [EMPTY_FIELD_VALUE];
  }
}

// Sort headings functions
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
function axisHeadingsSort(axisHeadingsSet, attribute) {
  // Track whether EMPTY_FIELD_VALUE is present, and ensure that
  // it is sorted to the first position even for custom fields
  const noHeaderValueIsFound = axisHeadingsSet.delete(EMPTY_FIELD_VALUE);
  let axisHeadingsList = [...axisHeadingsSet];
  let sorter;
  if (axisHeadingsSet.has(attribute)) {
    sorter = gridHeadings.get(attribute).sorter;
  }
  if (sorter) {
    axisHeadingsList = sorter(axisHeadingsList);
  } else {
    axisHeadingsList.sort();
  }
  if (noHeaderValueIsFound) {
    axisHeadingsList.push(EMPTY_FIELD_VALUE);
  }
  return axisHeadingsList;
}

// Outer function that runs each custom extractor function
export function extractGridData(issues, xAttribute, yAttribute) {
  const gridData = {
    xHeadings: [],
    yHeadings: [],
    sortedIssues: new Map(),
  };
  const xAxisHeadingsSet = new Set();
  const yAxisHeadingsSet = new Set();

  let xExtractor;
  let yExtractor;
  let xKeysAdded = [];
  let yKeysAdded = [];
  if (gridHeadings.has(xAttribute)) {
    xExtractor = gridHeadings.get(xAttribute).extractor;
  } else {
    xAxisHeadingsSet.add(DEFAULT_HEADER_VALUE);
    xKeysAdded.push(DEFAULT_HEADER_VALUE);
  }
  if (gridHeadings.has(yAttribute)) {
    yExtractor = gridHeadings.get(yAttribute).extractor;
  } else {
    yAxisHeadingsSet.add(DEFAULT_HEADER_VALUE);
    yKeysAdded.push(DEFAULT_HEADER_VALUE);
  }

  for (const issue of issues) {
    if (xExtractor) {
      xKeysAdded = xExtractor(issue);
      for (const key of xKeysAdded) {
        xAxisHeadingsSet.add(key);
      }
    }
    if (yExtractor) {
      yKeysAdded = yExtractor(issue);
      for (const key of yKeysAdded) {
        yAxisHeadingsSet.add(key);
      }
    }

    // Find every combo of 'xKey-yKey' that the issue belongs to
    // and sort it into that cell
    for (const xKey of xKeysAdded) {
      for (const yKey of yKeysAdded) {
        const cellKey = xKey + '-' + yKey;
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

  gridData.xHeadings = axisHeadingsSort(xAxisHeadingsSet, xAttribute);
  gridData.yHeadings = axisHeadingsSort(yAxisHeadingsSet, yAttribute);

  return gridData;
}
