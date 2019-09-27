// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {parseColSpec, stringValuesForIssueField} from './issue-fields.js';
import sinon from 'sinon';

let issue;
let clock;

describe('parseColSpec', () => {
  it('empty spec produces empty list', () => {
    assert.deepEqual(parseColSpec(),
        []);
    assert.deepEqual(parseColSpec(''),
        []);
    assert.deepEqual(parseColSpec(' + + + '),
        []);
    assert.deepEqual(parseColSpec('          '),
        []);
    assert.deepEqual(parseColSpec('+++++'),
        []);
  });

  it('parses spec correctly', () => {
    assert.deepEqual(parseColSpec('ID+Summary+AllLabels+Priority'),
        ['ID', 'Summary', 'AllLabels', 'Priority']);
  });

  it('parses spaces correctly', () => {
    assert.deepEqual(parseColSpec('ID Summary AllLabels Priority'),
        ['ID', 'Summary', 'AllLabels', 'Priority']);
    assert.deepEqual(parseColSpec('ID + Summary + AllLabels + Priority'),
        ['ID', 'Summary', 'AllLabels', 'Priority']);
    assert.deepEqual(parseColSpec('ID   Summary AllLabels     Priority'),
        ['ID', 'Summary', 'AllLabels', 'Priority']);
  });

  it('spec parsing preserves dashed parameters', () => {
    assert.deepEqual(parseColSpec('ID+Summary+Test-Label+Another-Label'),
        ['ID', 'Summary', 'Test-Label', 'Another-Label']);
  });
});

describe('stringValuesForIssueField', () => {
  describe('built-in fields', () => {
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
        componentModifiedTimestamp: initialTime - 60, // a minute ago
        statusModifiedTimestamp: initialTime - 60, // a minute ago
        ownerModifiedTimestamp: initialTime - 60, // a minute ago
        statusRef: {status: 'Duplicate'},
        mergedIntoIssueRef: {localId: 31, projectName: 'chromium'},
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

    it('computes strings for ComponentModified', () => {
      const fieldName = 'ComponentModified';

      assert.deepEqual(stringValuesForIssueField(issue, fieldName),
          ['a minute ago']);
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

    it('computes strings for Status', () => {
      const fieldName = 'Status';

      assert.deepEqual(stringValuesForIssueField(issue, fieldName),
          ['Duplicate']);
    });

    it('computes strings for StatusModified', () => {
      const fieldName = 'StatusModified';

      assert.deepEqual(stringValuesForIssueField(issue, fieldName),
          ['a minute ago']);
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

    it('computes strings for OwnerModified', () => {
      const fieldName = 'OwnerModified';

      assert.deepEqual(stringValuesForIssueField(issue, fieldName),
          ['a minute ago']);
    });

    it('computes strings for Opened', () => {
      const fieldName = 'Opened';

      assert.deepEqual(stringValuesForIssueField(issue, fieldName),
          ['a day ago']);
    });
  });

  describe('custom approval fields', () => {
    beforeEach(() => {
      issue = {
        localId: 33,
        projectName: 'bird',
        approvalValues: [
          {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Goose-Approval'},
            approverRefs: []},
          {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Chicken-Approval'},
            status: 'APPROVED'},
          {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Dodo-Approval'},
            status: 'NEED_INFO', approverRefs: [{displayName: 'kiwi@bird.test'},
              {displayName: 'mini-dino@bird.test'}],
          },
        ],
      };
    });

    it('handles approval approver columns', () => {
      const projectName = 'bird';
      const fieldDefMap = new Map([
        ['goose-approval', {
          fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Goose-Approval'}}],
        ['chicken-approval', {
          fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Chicken-Approval'}}],
        ['dodo-approval', {
          fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Dodo-Approval'}}],
      ]);
      assert.deepEqual(stringValuesForIssueField(
          issue, 'goose-approval-approver',
          projectName, fieldDefMap), []);
      assert.deepEqual(stringValuesForIssueField(
          issue, 'chicken-approval-approver',
          projectName, fieldDefMap), []);
      assert.deepEqual(stringValuesForIssueField(
          issue, 'dodo-approval-approver',
          projectName, fieldDefMap), ['kiwi@bird.test', 'mini-dino@bird.test']);
    });
    it('handles approval value columns', () => {
      const projectName = 'bird';
      const fieldDefMap = new Map([
        ['goose-approval', {
          fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Goose-Approval'}}],
        ['chicken-approval', {
          fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Chicken-Approval'}}],
        ['dodo-approval', {
          fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Dodo-Approval'}}],
      ]);
      assert.deepEqual(stringValuesForIssueField(issue, 'goose-approval',
          projectName, fieldDefMap), ['NotSet']);
      assert.deepEqual(stringValuesForIssueField(issue, 'chicken-approval',
          projectName, fieldDefMap), ['Approved']);
      assert.deepEqual(stringValuesForIssueField(issue, 'dodo-approval',
          projectName, fieldDefMap), ['NeedInfo']);
    });
  });

  describe('custom fields', () => {
    beforeEach(() => {
      issue = {
        localId: 33,
        projectName: 'chromium',
        fieldValues: [
          {fieldRef: {type: 'STR_TYPE', fieldName: 'aString'}, value: 'test'},
          {fieldRef: {type: 'STR_TYPE', fieldName: 'aString'}, value: 'test2'},
          {fieldRef: {type: 'ENUM_TYPE', fieldName: 'ENUM'}, value: 'a-value'},
          {fieldRef: {type: 'INT_TYPE', fieldId: '6', fieldName: 'Cow-Number'},
            phaseRef: {phaseName: 'Cow-Phase'},
            value: '55'},
          {fieldRef: {type: 'INT_TYPE', fieldId: '6', fieldName: 'Cow-Number'},
            phaseRef: {phaseName: 'Cow-Phase'},
            value: '54'},
          {fieldRef: {type: 'INT_TYPE', fieldId: '6', fieldName: 'Cow-Number'},
            phaseRef: {phaseName: 'MilkCow-Phase'},
            value: '56'},
        ],
      };
    });

    it('gets values for custom fields', () => {
      const projectName = 'chromium';
      const fieldDefMap = new Map([
        ['astring', {fieldRef: {type: 'STR_TYPE', fieldName: 'aString'}}],
        ['enum', {fieldRef: {type: 'ENUM_TYPE', fieldName: 'ENUM'}}],
        ['cow-number', {
          fieldRef: {type: 'INT_TYPE', fieldName: 'Cow-Number'},
          bool_is_phase_field: true, is_multivalued: true}],
      ]);
      assert.deepEqual(stringValuesForIssueField(issue, 'aString',
          projectName, fieldDefMap), ['test', 'test2']);
      assert.deepEqual(stringValuesForIssueField(issue, 'enum',
          projectName, fieldDefMap), ['a-value']);
      assert.deepEqual(stringValuesForIssueField(issue, 'cow-phase.cow-number',
          projectName, fieldDefMap), ['55', '54']);
      assert.deepEqual(stringValuesForIssueField(issue,
          'milkcow-phase.cow-number', projectName, fieldDefMap), ['56']);
    });

    it('custom fields get precedence over label fields', () => {
      const projectName = 'chromium';
      const fieldDefMap = new Map([
        ['astring', {fieldRef: {type: 'STR_TYPE', fieldName: 'aString'}}],
      ]);
      issue.labelRefs = [{label: 'aString-ignore'}];
      const labelPrefixSet = new Set(['aString']);
      assert.deepEqual(stringValuesForIssueField(issue, 'aString',
          projectName, fieldDefMap, labelPrefixSet), ['test', 'test2']);
    });
  });

  describe('label prefix fields', () => {
    beforeEach(() => {
      issue = {
        localId: 33,
        projectName: 'chromium',
        labelRefs: [
          {label: 'test-label'},
          {label: 'test-label-2'},
          {label: 'ignore-me'},
          {label: 'Milestone-UI'},
          {label: 'Milestone-Goodies'},
        ],
      };
    });

    it('gets values for label prefixes', () => {
      const projectName = 'chromium';
      const fieldDefMap = new Map();
      const labelPrefixSet = new Set(['test', 'milestone']);
      assert.deepEqual(stringValuesForIssueField(issue, 'test',
          projectName, fieldDefMap, labelPrefixSet), ['label', 'label-2']);
      assert.deepEqual(stringValuesForIssueField(issue, 'Milestone',
          projectName, fieldDefMap, labelPrefixSet), ['UI', 'Goodies']);
    });
  });
});
