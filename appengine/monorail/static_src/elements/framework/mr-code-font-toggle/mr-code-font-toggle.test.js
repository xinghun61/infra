// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import 'sinon';
import {assert} from 'chai';
import {MrCodeFontToggle} from './mr-code-font-toggle.js';
import {prpcClient} from 'prpc-client-instance.js';

let element;

describe('mr-code-font-toggle', () => {
  beforeEach(() => {
    element = document.createElement('mr-code-font-toggle');
    document.body.appendChild(element);
    sinon.stub(prpcClient, 'call').returns(Promise.resolve({}));
  });

  afterEach(() => {
    document.body.removeChild(element);
    prpcClient.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrCodeFontToggle);
  });

  it('toggle font', () => {
    element.userDisplayName = 'test@example.com';
    const chopsToggle = element.shadowRoot.querySelector('chops-toggle');
    const label = chopsToggle.shadowRoot.querySelector('label');

    label.click(); // Toggle it on.
    assert.deepEqual(prpcClient.call.getCall(0).args, [
      'monorail.Users',
      'SetUserPrefs',
      {prefs: [{name: 'code_font', value: 'true'}]},
    ]);
    assert.isTrue(prpcClient.call.calledOnce);

    element.prefs = new Map([['code_font', 'true']]);
    label.click(); // Toggle it off.
    assert.deepEqual(prpcClient.call.getCall(1).args, [
      'monorail.Users',
      'SetUserPrefs',
      {prefs: [{name: 'code_font', value: 'false'}]},
    ]);
    assert.isTrue(prpcClient.call.calledTwice);
  });
});
