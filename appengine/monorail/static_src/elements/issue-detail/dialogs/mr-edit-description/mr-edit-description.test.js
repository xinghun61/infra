// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditDescription} from './mr-edit-description.js';
import sinon from 'sinon';
import * as issue from 'elements/reducers/issue.js';


let element;

suite('mr-edit-description', () => {
  setup(() => {
    element = document.createElement('mr-edit-description');
    document.body.appendChild(element);
    element.comments = [
      {
        descriptionNum: 1,
        content: 'first description',
      },
      {
        content: 'first comment',
      },
      {
        descriptionNum: 1,
        content: '<b>last</b> description',
      },
      {
        descriptionNum: 1,
        content: 'first foo survey',
        approvalRef: {
          fieldName: 'foo',
        },
      },
      {
        content: 'second comment',
      },
      {
        descriptionNum: 1,
        content: 'last foo survey',
        approvalRef: {
          fieldName: 'foo',
        },
      },
      {
        descriptionNum: 1,
        content: 'bar survey',
        approvalRef: {
          fieldName: 'bar',
        },
      },
      {
        content: 'third comment',
      },
    ];

    window.prpcClient = {
      call: () => Promise.resolve({}),
    };
    sinon.spy(window.prpcClient, 'call');
    sinon.spy(issue.update);
  });

  teardown(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, MrEditDescription);
  });

  test('selects last issue description', async () => {
    element._fieldName = '';
    element.reset();

    await element.updateComplete;

    assert.equal(element._displayedContent, 'last description');
    assert.equal(element._displayedTitle, 'Description');
  });

  test('selects last survey', async () => {
    element._fieldName = 'foo';
    element.reset();

    await element.updateComplete;

    assert.equal(element._displayedContent, 'last foo survey');
    assert.equal(element._displayedTitle, 'foo Survey');
  });

  test('toggle sendEmail', async () => {
    element.reset();
    await element.updateComplete;

    const sendEmail = element.shadowRoot.querySelector('#sendEmail');

    await sendEmail.updateComplete;

    sendEmail.click();
    await element.updateComplete;
    assert.isFalse(element._sendEmail);

    sendEmail.click();
    await element.updateComplete;
    assert.isTrue(element._sendEmail);

    sendEmail.click();
    await element.updateComplete;
    assert.isFalse(element._sendEmail);
  });
});
