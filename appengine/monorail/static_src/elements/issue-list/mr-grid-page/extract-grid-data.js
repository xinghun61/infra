// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {extractTypeForIssue} from '../../reducers/type.js';
import {issueRefToString} from '../../shared/converters.js';

const gridHeadings = new Map();
const EMPTY_HEADER_VALUE = '----';

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

function extractBlockedHeadings(issue, keysSet) {
  if (issue.blockedOnIssueRefs) {
    keysSet.add('Yes');
  } else if (!issue.blockedOnIssueRefs) {
    keysSet.add('No');
  }
}

function extractBlockedOnHeadings(issue, keysSet) {
  if (!issue.blockedOnIssueRefs) {
    keysSet.add(EMPTY_HEADER_VALUE);
  } else {
    for (const blocked of issue.blockedOnIssueRefs) {
      const issueKey = issueRefToString(blocked, '');
      keysSet.add(issueKey);
    }
  }
}

function extractBlockingHeadings(issue, keysSet) {
  if (!issue.blockingIssueRefs) {
    keysSet.add(EMPTY_HEADER_VALUE);
  } else {
    for (const blocking of issue.blockingIssueRefs) {
      const issueKey = issueRefToString(blocking, '');
      keysSet.add(issueKey);
    }
  }
}

function extractComponentHeadings(issue, keysSet) {
  if (!issue.componentRefs) {
    keysSet.add(EMPTY_HEADER_VALUE);
  } else {
    for (const component of issue.componentRefs) {
      keysSet.add(component.path);
    }
  }
}

function extractReporterHeadings(issue, keysSet) {
  keysSet.add(issue.reporterRef.displayName);
}

function extractStarsHeadings(issue, keysSet) {
  keysSet.add(issue.starCount);
}

function extractStatusHeadings(issue, keysSet) {
  keysSet.add(issue.statusRef.status);
}

function extractTypeHeadings(issue, keysSet) {
  const labelRefs = issue.labelRefs;
  const fieldValues = issue.fieldValues;
  const type = extractTypeForIssue(fieldValues, labelRefs);
  if (type) {
    keysSet.add(type);
  } else {
    keysSet.add(EMPTY_HEADER_VALUE);
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

function axisHeadingsSort(axisHeadingsSet, attribute) {
  // Track whether EMPTY_HEADER_VALUE is present, and ensure that
  // it is sorted to the first position even for custom fields
  const noHeaderValueIsFound = axisHeadingsSet.delete(EMPTY_HEADER_VALUE);
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
    axisHeadingsList.unshift(EMPTY_HEADER_VALUE);
  }
  return axisHeadingsList;
}

// Outer function that runs each custom extractor function
export function extractGridData(issues, xAttribute, yAttribute) {
  const gridData = {
    xHeadings: [],
    yHeadings: [],
  };
  const xAxisHeadingsSet = new Set();
  const yAxisHeadingsSet = new Set();

  let xExtractor;
  let yExtractor;
  if (gridHeadings.has(xAttribute)) {
    xExtractor = gridHeadings.get(xAttribute).extractor;
  } else {
    xAxisHeadingsSet.add('All');
  }
  if (gridHeadings.has(yAttribute)) {
    yExtractor = gridHeadings.get(yAttribute).extractor;
  } else {
    yAxisHeadingsSet.add('All');
  }

  for (const issue of issues) {
    if (xExtractor) {
      xExtractor(issue, xAxisHeadingsSet);
    }
    if (yExtractor) {
      yExtractor(issue, yAxisHeadingsSet);
    }
  }

  gridData.xHeadings = axisHeadingsSort(xAxisHeadingsSet, xAttribute);
  gridData.yHeadings = axisHeadingsSort(yAxisHeadingsSet, yAttribute);

  return gridData;
}
