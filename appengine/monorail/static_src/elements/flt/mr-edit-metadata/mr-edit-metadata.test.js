// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrEditMetadata} from './mr-edit-metadata.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {resetState} from '../../redux/redux-mixin.js';
import {ISSUE_EDIT_PERMISSION} from '../../shared/permissions.js';


let element;

suite('mr-edit-metadata', () => {
  setup(() => {
    element = document.createElement('mr-edit-metadata');
    element.issuePermissions = ['editissue'];
    document.body.appendChild(element);

    // Disable Redux state mapping for testing.
    MrEditMetadata.mapStateToProps = () => {};
    sinon.stub(element, 'dispatchAction');
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction.restore();
    element.dispatchAction(resetState());
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

  test('not changing status produces no delta', () => {
    element.statuses = [
      {'status': 'Duplicate'},
    ];
    element.status = 'Duplicate';
    element.mergedInto = {
      projectName: 'chromium',
      localId: 1234,
    };
    element.projectName = 'chromium';

    flush();

    assert.deepEqual(element.getDelta(), {});
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
      mergedIntoRef: {
        projectName: 'chromium',
        localId: 1234,
      },
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
    element.fieldValueMap = new Map([['fakeField', ['prev value']]]);
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

    element.shadowRoot.querySelector('#testFieldInput').setValue('test value');
    element.shadowRoot.querySelector('#fakeFieldInput').setValue('');
    assert.deepEqual(element.getDelta(), {
      fieldValsAdd: [
        {
          fieldRef: {
            fieldName: 'testField',
            fieldId: 1,
          },
          value: 'test value',
        },
      ],
      fieldValsRemove: [
        {
          fieldRef: {
            fieldName: 'fakeField',
            fieldId: 2,
          },
          value: 'prev value',
        },
      ],
    });
  });

  test('changing approvers produces delta', () => {
    element.isApproval = true;
    element.hasApproverPrivileges = true;
    element.approvers = [
      {displayName: 'foo@example.com'},
      {displayName: 'bar@example.com'},
      {displayName: 'baz@example.com'},
    ];

    flush();

    element.shadowRoot.querySelector('#approversInput').setValue(
      ['chicken@example.com', 'foo@example.com', 'dog@example.com']);
    flush();

    assert.deepEqual(element.getDelta(), {
      approverRefsAdd: [
        {displayName: 'chicken@example.com'},
        {displayName: 'dog@example.com'},
      ],
      approverRefsRemove: [
        {displayName: 'bar@example.com'},
        {displayName: 'baz@example.com'},
      ],
    });
  });

  test('changing blockedon produces delta change', () => {
    element.blockedOn = [
      {projectName: 'chromium', localId: '1234'},
      {projectName: 'monorail', localId: '4567'},
    ];
    element.projectName = 'chromium';

    flush();

    const blockedOnInput = element.shadowRoot.querySelector('#blockedOnInput');
    blockedOnInput.setValue(['1234', 'v8:5678']);

    flush();

    assert.deepEqual(element.getDelta(), {
      blockedOnRefsAdd: [{
        projectName: 'v8',
        localId: 5678,
      }],
      blockedOnRefsRemove: [{
        projectName: 'monorail',
        localId: 4567,
      }],
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

    flush();

    assert.deepEqual(element.getDelta(), {
      fieldValsAdd: [
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

  test('adding components produces delta', () => {
    element.isApproval = false;
    element.issuePermissions = [ISSUE_EDIT_PERMISSION];

    flush();

    const compInput = element.shadowRoot.querySelector('#componentsInput');

    compInput.setValue(['Hello>World']);
    flush();

    assert.deepEqual(element.getDelta(), {
      compRefsAdd: [
        {path: 'Hello>World'},
      ],
    });

    compInput.setValue(['Hello>World', 'Test', 'Multi']);
    flush();

    assert.deepEqual(element.getDelta(), {
      compRefsAdd: [
        {path: 'Hello>World'},
        {path: 'Test'},
        {path: 'Multi'},
      ],
    });

    compInput.setValue([]);
    flush();

    assert.deepEqual(element.getDelta(), {});
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

    const uploader = element.shadowRoot.querySelector('mr-upload');
    uploader.files = [
      {name: 'test.png'},
      {name: 'rutabaga.png'},
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

  test('no edit issue permission', () => {
    element.issuePermissions = [];
    flush();

    assert.isNull(
      element.shadowRoot.querySelector('#inputGrid'));
    assert.isNull(
      element.shadowRoot.querySelector('#summaryInput'));
  });

  test('duplicate issue is rendered correctly', () => {
    element.statuses = [
      {'status': 'Duplicate'},
    ];
    element.status = 'Duplicate';
    element.projectName = 'chromium';
    element.mergedInto = {
      projectName: 'chromium',
      localId: 1234,
    };

    flush();

    const statusComponent = element.shadowRoot.querySelector(
      '#statusInput');
    const root = statusComponent.shadowRoot;
    assert.equal(
      root.querySelector('#mergedIntoInput').getValue(), '1234');
  });

  test('duplicate issue on different project is rendered correctly', () => {
    element.statuses = [
      {'status': 'Duplicate'},
    ];
    element.status = 'Duplicate';
    element.projectName = 'chromium';
    element.mergedInto = {
      projectName: 'monorail',
      localId: 1234,
    };

    flush();

    const statusComponent = element.shadowRoot.querySelector(
      '#statusInput');
    const root = statusComponent.shadowRoot;
    assert.equal(
      root.querySelector('#mergedIntoInput').getValue(), 'monorail:1234');
  });

  test('blocking issues are rendered correctly', () => {
    element.blocking = [
      {projectName: 'chromium', localId: '1234'},
      {projectName: 'monorail', localId: '4567'},
    ];
    element.projectName = 'chromium';

    flush();

    const blockingInput = element.shadowRoot.querySelector('#blockingInput');

    assert.deepEqual(['1234', 'monorail:4567'], blockingInput.getValues());
  });
});
