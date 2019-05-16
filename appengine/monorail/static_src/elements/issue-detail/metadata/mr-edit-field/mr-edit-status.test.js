// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditStatus} from './mr-edit-status.js';


let element;

describe('mr-edit-status', () => {
  beforeEach(() => {
    element = document.createElement('mr-edit-status');
    element.statuses = [
      {'status': 'New'},
      {'status': 'Old'},
      {'status': 'Duplicate'},
    ];
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrEditStatus);
  });

  it('delta empty when no changes', () => {
    assert.deepEqual(element.delta, {});
  });

  it('change status', async () => {
    element.initialStatus = 'New';

    await element.updateComplete;

    const statusInput = element.shadowRoot.querySelector('select');
    statusInput.value = 'Old';
    statusInput.dispatchEvent(new Event('change'));

    await element.updateComplete;

    assert.deepEqual(element.delta, {status: 'Old'});
  });

  it('mark as duplicate', async () => {
    element.initialStatus = 'New';

    await element.updateComplete;

    const statusInput = element.shadowRoot.querySelector('select');
    statusInput.value = 'Duplicate';
    statusInput.dispatchEvent(new Event('change'));

    await element.updateComplete;

    element.shadowRoot.querySelector('#mergedIntoInput').setValue('proj:123');
    assert.deepEqual(element.delta, {
      status: 'Duplicate',
      mergedInto: 'proj:123',
    });
  });

  it('remove mark as duplicate', async () => {
    element.initialStatus = 'Duplicate';
    element.mergedInto = 'chromium:1234';

    await element.updateComplete;

    const statusInput = element.shadowRoot.querySelector('select');
    statusInput.value = 'New';
    statusInput.dispatchEvent(new Event('change'));

    await element.updateComplete;

    assert.deepEqual(element.delta, {
      status: 'New',
      mergedInto: '',
    });
  });
});
