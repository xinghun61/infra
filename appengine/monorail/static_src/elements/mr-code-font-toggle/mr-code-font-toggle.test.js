// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrCodeFontToggle} from './mr-code-font-toggle.js';
import {actionType} from '../redux/redux-mixin.js';

let element;

suite('mr-code-font-toggle', () => {

  setup(() => {
    element = document.createElement('mr-code-font-toggle');
    document.body.appendChild(element);
    window.prpcClient = {
      call: () => Promise.resolve({}),
    };
    sinon.spy(window.prpcClient, 'call');
    MrCodeFontToggle.mapStateToProps = () => {};
  });

  teardown(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
    element.dispatchAction({type: actionType.RESET_STATE});
  });

  test('initializes', () => {
    assert.instanceOf(element, MrCodeFontToggle);
  });

  test('toggle font', () => {
    element.userDisplayName = 'test@example.com';
    const chopsToggle = element.shadowRoot.querySelector('chops-toggle');
    const label = chopsToggle.shadowRoot.querySelector('label');

    label.click();  // Toggle it on.
    assert.deepEqual(window.prpcClient.call.getCall(0).args, [
      'monorail.Users',
      'SetUserPrefs',
      {prefs: [{name: 'code_font', value: 'true'}]},
    ]);
    assert.isTrue(window.prpcClient.call.calledOnce);

    element.prefs = new Map([['code_font', 'true']]);
    label.click();  // Toggle it off.
    assert.deepEqual(window.prpcClient.call.getCall(1).args, [
      'monorail.Users',
      'SetUserPrefs',
      {prefs: [{name: 'code_font', value: 'false'}]},
    ]);
    assert.isTrue(window.prpcClient.call.calledTwice);
  });
});
