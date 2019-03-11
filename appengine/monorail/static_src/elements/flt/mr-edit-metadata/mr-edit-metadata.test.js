// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditMetadata} from './mr-edit-metadata.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {actionType} from '../../redux/redux-mixin.js';


let element;

suite('mr-edit-metadata', () => {
  setup(() => {
    element = document.createElement('mr-edit-metadata');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction({type: actionType.RESET_STATE});
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

    const statusComponent = element.shadowRoot.querySelector('#statusInput');
    const root = statusComponent.shadowRoot;
    root.querySelector('#statusInput').value = 'Old';
    assert.deepEqual(element.getDelta(), {
      status: 'Old',
    });
  });

  test('changing status to duplicate produces delta change', () => {
    element.statuses = [
      {'status': 'New'},
      {'status': 'Duplicate'},
    ];
    element.status = 'New';

    flush();

    const statusComponent = element.shadowRoot.querySelector(
      '#statusInput');
    const root = statusComponent.shadowRoot;
    const statusInput = root.querySelector('#statusInput');
    statusInput.value = 'Duplicate';
    statusInput.dispatchEvent(new Event('change'));

    flush();

    root.querySelector('#mergedIntoInput').setValue(
      'chromium:1234');
    assert.deepEqual(element.getDelta(), {
      status: 'Duplicate',
      mergedInto: 'chromium:1234',
    });
  });

  test('changing summary produces delta change', () => {
    element.summary = 'Old summary';

    flush();

    element.shadowRoot.querySelector(
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

    element.shadowRoot.querySelector(
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

    element.shadowRoot.querySelector(
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

  test('reset empties form values', () => {
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

    const uploader = element.shadowRoot.querySelector('vaadin-upload');
    uploader.files = [
      {name: 'test.png', progress: 0},
      {name: 'rutabaga.png', progress: 0},
    ];

    element.shadowRoot.querySelector('#testFieldInput').setValue('testy test');
    element.shadowRoot.querySelector('#fakeFieldInput').setValue('hello world');

    element.reset();

    assert.lengthOf(element.shadowRoot.querySelector(
      '#testFieldInput').getValue(), 0);
    assert.lengthOf(element.shadowRoot.querySelector(
      '#fakeFieldInput').getValue(), 0);
    assert.lengthOf(uploader.files, 0);
  });
});
