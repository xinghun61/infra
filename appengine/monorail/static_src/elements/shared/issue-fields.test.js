// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {stringValuesForIssueField} from './issue-fields.js';
import sinon from 'sinon';

let issue;
let clock;

describe('stringValuesForIssueField', () => {
  beforeEach(() => {
    // Set clock to some specified date for relative time.
    const initialTime = 365 * 24 * 60 * 60;

    clock = sinon.useFakeTimers({
      now: new Date(initialTime * 1000),
      shouldAdvanceTime: false,
    });

    issue = {
      localId: 33,
      projectName: 'chromium',
      summary: 'Test summary',
      attachmentCount: 22,
      starCount: 2,
      componentRefs: [{path: 'Infra'}, {path: 'Monorail>UI'}],
      blockedOnIssueRefs: [{localId: 30, projectName: 'chromium'}],
      blockingIssueRefs: [{localId: 60, projectName: 'chromium'}],
      labelRefs: [{label: 'Restrict-View-Google'}, {label: 'Type-Defect'}],
      reporterRef: {displayName: 'test@example.com'},
      ccRefs: [{displayName: 'test@example.com'}],
      ownerRef: {displayName: 'owner@example.com'},
      closedTimestamp: initialTime - 120, // 2 minutes ago
      modifiedTimestamp: initialTime - 60, // a minute ago
      openedTimestamp: initialTime - 24 * 60 * 60, // a day ago
      statusRef: {status: 'Duplicate'},
      mergedInto: {localId: 31, projectName: 'chromium'},
    };
  });

  afterEach(() => {
    clock.restore();
  });

  it('computes strings for ID', () => {
    const fieldName = 'ID';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['chromium:33']);
  });

  it('computes strings for Project', () => {
    const fieldName = 'Project';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['chromium']);
  });

  it('computes strings for Attachments', () => {
    const fieldName = 'Attachments';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['22']);
  });

  it('computes strings for AllLabels', () => {
    const fieldName = 'AllLabels';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['Restrict-View-Google', 'Type-Defect']);
  });

  it('computes strings for Blocked when issue is blocked', () => {
    const fieldName = 'Blocked';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['Yes']);
  });

  it('computes strings for Blocked when issue is not blocked', () => {
    const fieldName = 'Blocked';
    issue.blockedOnIssueRefs = [];

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['No']);
  });

  it('computes strings for BlockedOn', () => {
    const fieldName = 'BlockedOn';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['chromium:30']);
  });

  it('computes strings for Blocking', () => {
    const fieldName = 'Blocking';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['chromium:60']);
  });

  it('computes strings for CC', () => {
    const fieldName = 'CC';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['test@example.com']);
  });

  it('computes strings for Closed', () => {
    const fieldName = 'Closed';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['2 minutes ago']);
  });

  it('computes strings for Component', () => {
    const fieldName = 'Component';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['Infra', 'Monorail>UI']);
  });

  it('computes strings for MergedInto', () => {
    const fieldName = 'MergedInto';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['chromium:31']);
  });

  it('computes strings for Modified', () => {
    const fieldName = 'Modified';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['a minute ago']);
  });

  it('computes strings for Reporter', () => {
    const fieldName = 'Reporter';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['test@example.com']);
  });

  it('computes strings for Stars', () => {
    const fieldName = 'Stars';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['2']);
  });

  it('computes strings for Summary', () => {
    const fieldName = 'Summary';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['Test summary']);
  });

  it('computes strings for Type', () => {
    const fieldName = 'Type';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['Defect']);
  });

  it('computes strings for Owner', () => {
    const fieldName = 'Owner';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['owner@example.com']);
  });

  it('computes strings for Opened', () => {
    const fieldName = 'Opened';

    assert.deepEqual(stringValuesForIssueField(issue, fieldName),
      ['a day ago']);
  });
});
