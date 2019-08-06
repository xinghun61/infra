// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import * as project from './project.js';
import {fieldTypes} from 'elements/shared/issue-fields.js';

describe('project', () => {
  it('fieldDefs', () => {
    assert.deepEqual(project.fieldDefs({project: {}}), []);
    assert.deepEqual(project.fieldDefs({project: {config: {}}}), []);
    assert.deepEqual(project.fieldDefs({
      project: {config: {fieldDefs: [{fieldRef: {fieldName: 'test'}}]}},
    }), [{fieldRef: {fieldName: 'test'}}]);
  });

  it('labelDefMap', () => {
    assert.deepEqual(project.labelDefMap({project: {}}), new Map());
    assert.deepEqual(project.labelDefMap({project: {config: {}}}), new Map());
    assert.deepEqual(project.labelDefMap({
      project: {config: {
        labelDefs: [
          {label: 'One'},
          {label: 'tWo'},
          {label: 'hello-world', docstring: 'hmmm'},
        ],
      }},
    }), new Map([
      ['one', {label: 'One'}],
      ['two', {label: 'tWo'}],
      ['hello-world', {label: 'hello-world', docstring: 'hmmm'}],
    ]));
  });

  it('labelPrefixOptions', () => {
    assert.deepEqual(project.labelPrefixOptions({project: {}}), new Map());
    assert.deepEqual(project.labelPrefixOptions({project: {config: {}}}), new Map());
    assert.deepEqual(project.labelPrefixOptions({
      project: {config: {
        labelDefs: [
          {label: 'One'},
          {label: 'tWo'},
          {label: 'tWo-options'},
          {label: 'hello-world', docstring: 'hmmm'},
          {label: 'hello-me', docstring: 'hmmm'},
        ],
      }},
    }), new Map([
      ['two', ['tWo', 'tWo-options']],
      ['hello', ['hello-world', 'hello-me']],
    ]));
  });

  it('labelPrefixFields', () => {
    assert.deepEqual(project.labelPrefixFields({project: {}}), []);
    assert.deepEqual(project.labelPrefixFields({project: {config: {}}}), []);
    assert.deepEqual(project.labelPrefixFields({
      project: {config: {
        labelDefs: [
          {label: 'One'},
          {label: 'tWo'},
          {label: 'tWo-options'},
          {label: 'hello-world', docstring: 'hmmm'},
          {label: 'hello-me', docstring: 'hmmm'},
        ],
      }},
    }), ['tWo', 'hello']);
  });

  it('enumFieldDefs', () => {
    assert.deepEqual(project.enumFieldDefs({project: {}}), []);
    assert.deepEqual(project.enumFieldDefs({project: {config: {}}}), []);
    assert.deepEqual(project.enumFieldDefs({
      project: {config: {fieldDefs: [
        {fieldRef: {fieldName: 'test'}},
        {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
        {fieldRef: {fieldName: 'ignore', type: fieldTypes.DATE_TYPE}},
      ]}},
    }), [{fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}}]);
  });

  it('optionsPerEnumField', () => {
    assert.deepEqual(project.optionsPerEnumField({project: {}}), new Map());
    assert.deepEqual(project.optionsPerEnumField({
      project: {config: {
        fieldDefs: [
          {fieldRef: {fieldName: 'ignore', type: fieldTypes.DATE_TYPE}},
          {fieldRef: {fieldName: 'eNum', type: fieldTypes.ENUM_TYPE}},
        ],
        labelDefs: [
          {label: 'enum-one'},
          {label: 'ENUM-tWo'},
          {label: 'not-enum-three'},
        ],
      }},
    }), new Map([
      ['enum', [
        {label: 'enum-one', optionName: 'one'},
        {label: 'ENUM-tWo', optionName: 'tWo'},
      ]],
    ]));
  });

  it('fieldDefsByApprovalName', () => {
    assert.deepEqual(project.fieldDefsByApprovalName({project: {}}), new Map());

    assert.deepEqual(project.fieldDefsByApprovalName({project: {config: {
      fieldDefs: [
        {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
        {fieldRef: {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
        {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
      ],
    }}}), new Map([
      ['ThisIsAnApproval', [
        {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
      ]],
      ['Legal', [
        {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
      ]],
    ]));
  });
});
