/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import {assert} from 'chai';
import {MrEditMetadata} from './mr-edit-metadata.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {dom} from '@polymer/polymer/lib/legacy/polymer.dom.js';


let element;

suite('mr-edit-metadata');

beforeEach(() => {
  element = document.createElement('mr-edit-metadata');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, MrEditMetadata);
});

test('delta empty when no changes', () => {
  assert.deepEqual(element.getDelta(), {});
});

test('toggling checkbox toggles sendEmail', () => {
  element.sendEmail = false;

  flush();
  const checkbox = element.shadowRoot.querySelector('#sendEmail');

  checkbox.click();
  assert.equal(checkbox.checked, true);
  assert.equal(element.sendEmail, true);

  checkbox.click();
  assert.equal(checkbox.checked, false);
  assert.equal(element.sendEmail, false);

  checkbox.click();
  assert.equal(checkbox.checked, true);
  assert.equal(element.sendEmail, true);
});

test('changing status produces delta change', () => {
  element.statuses = [
    {'status': 'New'},
    {'status': 'Old'},
    {'status': 'Test'},
  ];
  element.status = 'New';

  flush();

  dom(element.root).querySelector('#statusInput').value = 'Old';
  assert.deepEqual(element.getDelta(), {
    status: 'Old',
  });
});

test('changing summary produces delta change', () => {
  element.summary = 'Old summary';

  flush();

  dom(element.root).querySelector(
    '#summaryInput').value = 'newfangled fancy summary';
  assert.deepEqual(element.getDelta(), {
    summary: 'newfangled fancy summary',
  });
});

test('changing custom fields produces delta', () => {
  element.fieldDefs = [
    {
      fieldRef: {
        fieldName: 'testField',
        fieldId: 1,
      },
    },
    {
      fieldRef: {
        fieldName: 'fakeField',
        fieldId: 2,
      },
    },
  ];

  flush();

  dom(element.root).querySelector(
    '#testFieldInput').setValue('test value');
  assert.deepEqual(element.getDelta(), {
    fieldValuesAdded: [
      {
        fieldRef: {
          fieldName: 'testField',
          fieldId: 1,
        },
        value: 'test value',
      },
    ],
  });
});

test('_optionsForField computes options for fieldDef', () => {
  const labels = [
    {
      label: 'enumField-one',
    },
    {
      label: 'enumField-two',
    },
  ];

  assert.deepEqual(element._optionsForField(labels, 'enumField'), [
    {
      label: 'enumField-one',
      optionName: 'one',
    },
    {
      label: 'enumField-two',
      optionName: 'two',
    },
  ]);
});

test('changing enum fields produces delta', () => {
  element.fieldDefs = [
    {
      fieldRef: {
        fieldName: 'enumField',
        fieldId: 1,
        type: 'ENUM_TYPE',
      },
      isMultivalued: true,
    },
  ];
  element.projectConfig = {
    labelDefs: [
      {
        label: 'enumField-one',
      },
      {
        label: 'enumField-two',
        optionName: 'two',
      },
    ],
  };

  flush();

  dom(element.root).querySelector(
    '#enumFieldInput').setValue(['one', 'two']);
  assert.deepEqual(element.getDelta(), {
    fieldValuesAdded: [
      {
        fieldRef: {
          fieldName: 'enumField',
          fieldId: 1,
        },
        value: 'one',
      },
      {
        fieldRef: {
          fieldName: 'enumField',
          fieldId: 1,
        },
        value: 'two',
      },
    ],
  });
});

test('approver input appears when user has privileges', () => {
  assert.isNull(
    element.shadowRoot.querySelector('#approversInput'));
  element.isApproval = true;
  element.hasApproverPrivileges = true;

  flush();

  assert.isNotNull(
    element.shadowRoot.querySelector('#approversInput'));
});
