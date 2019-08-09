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

  it('toggling font does not save when user is not logged in', async () => {
    element.userDisplayName = undefined;
    element.prefs = new Map([]);

    await element.updateComplete;

    const chopsToggle = element.shadowRoot.querySelector('chops-toggle');

    chopsToggle.click(); // Toggle it on.
    await element.updateComplete;

    sinon.assert.notCalled(prpcClient.call);

    assert.deepEqual(element.prefs, new Map([['code_font', 'true']]));
  });

  it('toggling font to true saves result', async () => {
    element.userDisplayName = 'test@example.com';
    element.prefs = new Map([['code_font', 'false']]);

    await element.updateComplete;

    const chopsToggle = element.shadowRoot.querySelector('chops-toggle');

    chopsToggle.click(); // Toggle it on.
    await element.updateComplete;

    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Users',
        'SetUserPrefs',
        {prefs: [{name: 'code_font', value: 'true'}]});

    assert.deepEqual(element.prefs, new Map([['code_font', 'true']]));
  });

  it('toggling font to false saves result', async () => {
    element.userDisplayName = 'test@example.com';
    element.prefs = new Map([['code_font', 'true']]);

    await element.updateComplete;

    const chopsToggle = element.shadowRoot.querySelector('chops-toggle');

    chopsToggle.click(); // Toggle it off.
    await element.updateComplete;

    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Users',
        'SetUserPrefs',
        {prefs: [{name: 'code_font', value: 'false'}]});

    assert.deepEqual(element.prefs, new Map([['code_font', 'false']]));
  });
});
