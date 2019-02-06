// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {selectors} from './selectors.js';
import {fieldTypes} from '../shared/field-types.js';

suite('selectors');

test('viewedIssue', () => {
  assert.isUndefined(selectors.viewedIssue({}));
  assert.deepEqual(selectors.viewedIssue({issue: {localId: 100}}),
    {localId: 100});
});

test('fieldDefs', () => {
  assert.isUndefined(selectors.fieldDefs({}));
  assert.isUndefined(selectors.fieldDefs({projectConfig: {}}));
  assert.deepEqual(selectors.fieldDefs({
    projectConfig: {fieldDefs: [{fieldName: 'test'}]},
  }), [{fieldName: 'test'}]);
});

test('issueFieldValues', () => {
  assert.isUndefined(selectors.issueFieldValues({}));
  assert.isUndefined(selectors.issueFieldValues({issue: {}}));
  assert.deepEqual(selectors.issueFieldValues({
    issue: {fieldValues: [{value: 'v'}]},
  }), [{value: 'v'}]);
});

test('issueType', () => {
  assert.isUndefined(selectors.issueType({}));
  assert.isUndefined(selectors.issueType({issue: {}}));
  assert.isUndefined(selectors.issueType({
    issue: {fieldValues: [{value: 'v'}]},
  }));
  assert.deepEqual(selectors.issueType({
    issue: {fieldValues: [
      {fieldRef: {fieldName: 'IgnoreMe'}, value: 'v'},
      {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
    ]},
  }), 'Defect');
});

test('issueFieldValueMap', () => {
  assert.deepEqual(selectors.issueFieldValueMap({}), new Map());
  assert.deepEqual(selectors.issueFieldValueMap({issue: {
    fieldValues: [],
  }}), new Map());
  assert.deepEqual(selectors.issueFieldValueMap({
    issue: {fieldValues: [
      {fieldRef: {fieldName: 'hello'}, value: 'v1'},
      {fieldRef: {fieldName: 'hello'}, value: 'v2'},
      {fieldRef: {fieldName: 'world'}, value: 'v3'},
    ]},
  }), new Map([
    ['hello', ['v1', 'v2']],
    ['world', ['v3']],
  ]));
});

test('fieldDefsForIssue', () => {
  assert.deepEqual(selectors.fieldDefsForIssue({}), []);

  // Remove approval-related fields, regardless of issue.
  assert.deepEqual(selectors.fieldDefsForIssue({projectConfig: {
    fieldDefs: [
      {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
      {fieldRef: {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
      {fieldRef: {fieldName: 'LookAway', approvalName: 'ThisIsAnApproval'}},
      {fieldRef: {fieldName: 'phaseField'}, isPhaseField: true},
    ],
  }}), [
    {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
  ]);

  // Filter defs by applicableType.
  assert.deepEqual(selectors.fieldDefsForIssue({
    projectConfig: {
      fieldDefs: [
        {fieldRef: {fieldName: 'intyInt', type: fieldTypes.INT_TYPE}},
        {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
        {fieldRef: {fieldName: 'nonApplicable', type: fieldTypes.STR_TYPE},
          applicableType: 'None'},
        {fieldRef: {fieldName: 'defectsOnly', type: fieldTypes.STR_TYPE},
          applicableType: 'Defect'},
      ],
    },
    issue: {
      fieldValues: [
        {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
      ],
    },
  }), [
    {fieldRef: {fieldName: 'intyInt', type: fieldTypes.INT_TYPE}},
    {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
    {fieldRef: {fieldName: 'defectsOnly', type: fieldTypes.STR_TYPE},
      applicableType: 'Defect'},
  ]);
});

test('fieldDefsByApprovalName', () => {
  assert.deepEqual(selectors.fieldDefsByApprovalName({}), new Map());

  assert.deepEqual(selectors.fieldDefsByApprovalName({projectConfig: {
    fieldDefs: [
      {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
      {fieldRef: {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
      {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
      {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
      {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
    ],
  }}), new Map([
    ['ThisIsAnApproval', [
      {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
      {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
    ]],
    ['Legal', [
      {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
    ]],
  ]));
});
