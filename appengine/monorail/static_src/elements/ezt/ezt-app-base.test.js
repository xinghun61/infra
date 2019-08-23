// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {EztAppBase} from './ezt-app-base.js';


let element;

describe('ezt-app-base', () => {
  beforeEach(() => {
    element = document.createElement('ezt-app-base');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, EztAppBase);
  });

  it('fetches user data when userDisplayName set', async () => {
    sinon.stub(element, 'fetchUserData');

    element.userDisplayName = 'test@example.com';

    await element.updateComplete;

    sinon.assert.calledOnce(element.fetchUserData);
    sinon.assert.calledWith(element.fetchUserData, 'test@example.com');
  });
});
