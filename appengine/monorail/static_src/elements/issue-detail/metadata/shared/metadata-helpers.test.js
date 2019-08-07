// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {fieldDefsWithGroup, fieldValueMapKey,
  fieldDefsWithoutGroup, HARDCODED_FIELD_GROUPS} from './metadata-helpers.js';

const fieldDefs = [
  {
    fieldRef: {
      fieldName: 'Ignore',
      fieldId: 1,
    },
  },
  {
    fieldRef: {
      fieldName: 'DesignDoc',
      fieldId: 2,
    },
  },
];
const fieldGroups = HARDCODED_FIELD_GROUPS;

describe('metadata-helpers', () => {
  it('fieldValueMapKey', () => {
    assert.equal(fieldValueMapKey('test', 'two'), 'test two');

    assert.equal(fieldValueMapKey('noPhase'), 'nophase');
  });

  it('fieldDefsWithoutGroup ignores non applicable types', () => {
    assert.deepEqual(fieldDefsWithoutGroup(
      fieldDefs, fieldGroups, 'ungrouped-type'), fieldDefs);
  });

  it('fieldDefsWithoutGroup filters grouped fields', () => {
    assert.deepEqual(fieldDefsWithoutGroup(
      fieldDefs, fieldGroups, 'flt-launch'), [
      {
        fieldRef: {
          fieldName: 'Ignore',
          fieldId: 1,
        },
      },
    ]);
  });

  it('fieldDefsWithGroup filters by type', () => {
    const filteredGroupsList = [{
      groupName: 'Docs',
      fieldDefs: [
        {
          fieldRef: {
            fieldName: 'DesignDoc',
            fieldId: 2,
          },
        },
      ],
    }];

    assert.deepEqual(
      fieldDefsWithGroup(fieldDefs, fieldGroups, 'Not-FLT-Launch'), []);

    assert.deepEqual(fieldDefsWithGroup(fieldDefs, fieldGroups, 'flt-launch'),
      filteredGroupsList);

    assert.deepEqual(fieldDefsWithGroup(fieldDefs, fieldGroups, 'FLT-LAUNCH'),
      filteredGroupsList);
  });
});
