// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {extractGridData} from './extract-grid-data.js';

describe('extract headings from x and y attributes', () => {
  // TODO(juliacordero): Uncomment once attachmentCount functionality
  // is re-enabled
  /* it('Extract headings from Attachments attribute', () => {
    const issues = [
      {'attachmentCount': '1'}, {'attachmentCount': '0'},
      {'attachmentCount': '1'},
    ];
    const data = extractGridData(issues, 'Attachments);
    assert.deepEqual(data, ['0', '1']);
  }); */

  it('Extract headings from Blocked attribute', () => {
    const issues = [
      {'blockedOnIssueRefs': ['testIssue']},
      {'otherIssueProperty': 'issueProperty'},
    ];
    const data = extractGridData(issues, 'Blocked', '');

    const expectedData = new Map();
    expectedData.set('Yes-All', [{'blockedOnIssueRefs': ['testIssue']}]);
    expectedData.set('No-All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['No', 'Yes']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });

  it('Extract headings from BlockedOn attribute', () => {
    const issues = [
      {'otherIssueProperty': 'issueProperty'},
      {'blockedOnIssueRefs': [
        {'localId': '3', 'projectName': 'test-projectB'}]},
      {'blockedOnIssueRefs': [
        {'localId': '3', 'projectName': 'test-projectA'}]},
      {'blockedOnIssueRefs': [
        {'localId': '3', 'projectName': 'test-projectA'}]},
      {'blockedOnIssueRefs': [
        {'localId': '1', 'projectName': 'test-projectA'}]},
    ];
    const data = extractGridData(issues, 'BlockedOn', '');

    const expectedData = new Map();
    expectedData.set('test-projectB:3-All', [{'blockedOnIssueRefs':
      [{'localId': '3', 'projectName': 'test-projectB'}]}]);
    expectedData.set('test-projectA:3-All', [{'blockedOnIssueRefs':
      [{'localId': '3', 'projectName': 'test-projectA'}]},
    {'blockedOnIssueRefs':
      [{'localId': '3', 'projectName': 'test-projectA'}]}]);
    expectedData.set('test-projectA:1-All', [{'blockedOnIssueRefs':
      [{'localId': '1', 'projectName': 'test-projectA'}]}]);
    expectedData.set('-----All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['test-projectA:1',
      'test-projectA:3', 'test-projectB:3', '----']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });

  it('Extract headings from Blocking attribute', () => {
    const issues = [
      {'otherIssueProperty': 'issueProperty'},
      {'blockingIssueRefs': [
        {'localId': '1', 'projectName': 'test-projectA'}]},
      {'blockingIssueRefs': [
        {'localId': '1', 'projectName': 'test-projectA'}]},
      {'blockingIssueRefs': [
        {'localId': '3', 'projectName': 'test-projectA'}]},
      {'blockingIssueRefs': [
        {'localId': '3', 'projectName': 'test-projectB'}]},
    ];
    const data = extractGridData(issues, 'Blocking', '');

    const expectedData = new Map();
    expectedData.set('test-projectA:1-All', [{'blockedOnIssueRefs':
      [{'localId': '1', 'projectName': 'test-projectA'}]},
    {'blockedOnIssueRefs':
      [{'localId': '1', 'projectName': 'test-projectA'}]}]);
    expectedData.set('test-projectA:3-All', [{'blockedOnIssueRefs':
      [{'localId': '3', 'projectName': 'test-projectA'}]}]);
    expectedData.set('test-projectB:3-All', [{'blockedOnIssueRefs':
      [{'localId': '3', 'projectName': 'test-projectB'}]}]);
    expectedData.set('-----All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['test-projectA:1',
      'test-projectA:3', 'test-projectB:3', '----']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });

  it('Extract headings from Component attribute', () => {
    const issues = [
      {'otherIssueProperty': 'issueProperty'},
      {'componentRefs': [{'path': 'UI'}]},
      {'componentRefs': [{'path': 'API'}]},
      {'componentRefs': [{'path': 'UI'}]},
    ];
    const data = extractGridData(issues, 'Component', '');

    const expectedData = new Map();
    expectedData.set('UI-All', [{'componentRefs': [{'path': 'UI'}]},
      {'componentRefs': [{'path': 'UI'}]}]);
    expectedData.set('API-All', [{'componentRefs': [{'path': 'API'}]}]);
    expectedData.set('-----All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['API', 'UI', '----']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });

  it('Extract headings from Reporter attribute', () => {
    const issues = [
      {'reporterRef': {'displayName': 'testA@google.com'}},
      {'reporterRef': {'displayName': 'testB@google.com'}},
    ];
    const data = extractGridData(issues, '', 'Reporter');

    const expectedData = new Map();
    expectedData.set('All-testA@google.com',
      [{'reporterRef': {'displayName': 'testA@google.com'}}]);
    expectedData.set('All-testB@google.com',
      [{'reporterRef': {'displayName': 'testB@google.com'}}]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['testA@google.com', 'testB@google.com']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });

  it('Extract headings from Stars attribute', () => {
    const issues = [
      {'starCount': '1'}, {'starCount': '6'}, {'starCount': '1'},
    ];
    const data = extractGridData(issues, '', 'Stars');

    const expectedData = new Map();
    expectedData.set('All-1', [{'starCount': '1'}, {'starCount': '1'}]);
    expectedData.set('All-6', [{'starCount': '6'}]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['1', '6']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });

  // TODO(juliacordero): sort these like the current grid view (?)
  it('Extract headings from Status attribute', () => {
    const issues = [
      {'statusRef': {'status': 'New'}},
      {'statusRef': {'status': 'Accepted'}},
      {'statusRef': {'status': 'New'}},
    ];
    const data = extractGridData(issues, '', 'Status');

    const expectedData = new Map();
    expectedData.set('All-Accepted', [{'statusRef': {'status': 'Accepted'}}]);
    expectedData.set('All-New', [{'statusRef': {'status': 'New'}},
      {'statusRef': {'status': 'New'}}]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['Accepted', 'New']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });

  it('Extract headings from the Type attribute', () => {
    const issues = [
      {'labelRefs': [{'label': 'Pri-2'}, {'label': 'Milestone-2000Q1'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Enhancement'}]},
    ];
    const data = extractGridData(issues, '', 'Type');

    const expectedData = new Map();
    expectedData.set('All-Defect', [{'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]}]);
    expectedData.set('All-Enhancement', [{'labelRefs':
      [{'label': 'Type-Enhancement'}]}]);
    expectedData.set('All-----', [{'labelRefs':
      [{'label': 'Pri-2'}, {'label': 'Milestone-2000Q1'}]}]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['Defect', 'Enhancement', '----']);
    assert.deepEqual(data.sortedIssues, expectedData);
  });
});
