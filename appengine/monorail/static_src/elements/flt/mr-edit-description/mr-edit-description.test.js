// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditDescription} from './mr-edit-description.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {actionCreator, actionType} from '../../redux/redux-mixin.js';


let element;

suite('mr-edit-descriptions', () => {
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
    sinon.spy(actionCreator, 'updateIssue');

    // Disable Redux state mapping for testing.
    MrEditDescription.mapStateToProps = () => {};
  });

  teardown(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
    actionCreator.updateIssue.restore();
    element.dispatchAction({type: actionType.RESET_STATE});
  });

  test('initializes', () => {
    assert.instanceOf(element, MrEditDescription);
  });

  test('selects last issue description', () => {
    element._fieldName = '';
    element.reset();
    flush();
    assert.equal(element._displayedContent, 'last description');
    assert.equal(element._displayedTitle, 'Description');
  });

  test('selects last survey', () => {
    element._fieldName = 'foo';
    element.reset();
    flush();
    assert.equal(element._displayedContent, 'last foo survey');
    assert.equal(element._displayedTitle, 'foo Survey');
  });

  test('toggle sendEmail', () => {
    element.reset();
    flush();
    const sendEmail = element.shadowRoot.querySelector('#sendEmail');

    sendEmail.click();
    assert.equal(element._sendEmail, false);
    sendEmail.click();
    assert.equal(element._sendEmail, true);
    sendEmail.click();
    assert.equal(element._sendEmail, false);
  });
});
