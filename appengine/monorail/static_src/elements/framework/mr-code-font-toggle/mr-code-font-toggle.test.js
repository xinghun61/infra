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

  it('toggle font', async () => {
    element.userDisplayName = 'test@example.com';

    await element.updateComplete;

    const chopsToggle = element.shadowRoot.querySelector('chops-toggle');

    chopsToggle.click(); // Toggle it on.
    await element.updateComplete;

    sinon.assert.calledWith(
      prpcClient.call,
      'monorail.Users',
      'SetUserPrefs',
      {prefs: [{name: 'code_font', value: 'true'}]});

    element.prefs = new Map([['code_font', 'true']]);
    chopsToggle.click(); // Toggle it off.
    await element.updateComplete;

    sinon.assert.calledWith(
      prpcClient.call,
      'monorail.Users',
      'SetUserPrefs',
      {prefs: [{name: 'code_font', value: 'false'}]});
  });
});
