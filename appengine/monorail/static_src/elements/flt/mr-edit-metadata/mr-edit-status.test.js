// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditStatus} from './mr-edit-status.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;

suite('mr-edit-status', () => {

  setup(() => {
    element = document.createElement('mr-edit-status');
    element.statuses = [
      {'status': 'New'},
      {'status': 'Old'},
      {'status': 'Duplicate'},
    ];
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrEditStatus);
  });

  test('delta empty when no changes', () => {
    assert.deepEqual(element.getDelta(), {});
  });

  test('change status', () => {
    element.status = 'New';

    flush();

    element.shadowRoot.querySelector('#statusInput').value = 'Old';
    assert.deepEqual(element.getDelta(), {
      status: 'Old',
    });
  });

  test('mark as duplicate', () => {
    element.status = 'New';

    flush();

    const statusInput = element.shadowRoot.querySelector('#statusInput');
    statusInput.value = 'Duplicate';
    statusInput.dispatchEvent(new Event('change'));

    flush();

    element.shadowRoot.querySelector('#mergedIntoInput').setValue('chromium:123');
    assert.deepEqual(element.getDelta(), {
      status: 'Duplicate',
      mergedIntoRef: {
        projectName: 'chromium',
        localId: 123,
      },
    });
  });

  test('remove mark as duplicate', () => {
    element.status = 'Duplicate';
    element.mergedInto = 'chromium:1234';

    flush();

    const statusInput = element.shadowRoot.querySelector('#statusInput');
    statusInput.value = 'New';
    statusInput.dispatchEvent(new Event('change'));

    flush();

    assert.deepEqual(element.getDelta(), {
      status: 'New',
      mergedIntoRef: {},
    });
  });
});
