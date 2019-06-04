// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {AnnouncementInput} from './announcement-input.js';
import sinon from 'sinon';
import {prpcClient} from 'prpc.js';

let element;
let prpcStub;

let createPromise;

suite('announcement-input', () => {
  setup(() => {
    prpcStub = sinon.stub(prpcClient, 'call');
    element = document.createElement('announcement-input');
    document.body.appendChild(element);
  });

  teardown(function() {
    prpcStub.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, AnnouncementInput);
  });

  test('test button updated on input', async () => {
    await element.updateComplete;

    const input = element.shadowRoot.querySelector('textarea');
    const button = element.shadowRoot.querySelector('button');
    assert.isTrue(button.disabled);

    input.value = 'new announcement';
    input.dispatchEvent(new Event('input'));
    await element.updateComplete; // element.disabled update

    assert.isNotTrue(button.disabled);

    input.value = '';
    input.dispatchEvent(new Event('input'));
    await element.updateComplete; // element.disabled update

    assert.isTrue(button.disabled);
  });

  test('create new announcement', async () => {
    createPromise = Promise.resolve({id: '123', creator: 'chicken'});
    prpcStub.returns(createPromise);

    await element.updateComplete;

    const input = element.shadowRoot.querySelector('textarea');
    const button = element.shadowRoot.querySelector('button');

    element.errorMessage = 'error message from previous attempt.';
    input.value = 'new announcement';
    input.dispatchEvent(new Event('input'));
    await element.updateComplete; // element.disabled update
    assert.isNotTrue(button.disabled);

    button.click();

    await createPromise;
    await element.updateComplete; // element.disabled update

    sinon.assert.calledOnce(prpcStub);
    sinon.assert.calledWith(
      prpcStub, 'dashboard.ChopsAnnouncements', 'CreateLiveAnnouncement');

    assert.equal(input.value, '');
    assert.equal(element.errorMessage, '');
    assert.isTrue(button.disabled);
  });
});
