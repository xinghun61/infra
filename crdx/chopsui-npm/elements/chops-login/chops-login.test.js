// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsLogin} from './index.js';
import {auditA11y} from '../../test-helpers';

let element;

suite('chops-login');

beforeEach(() => {
  element = document.createElement('chops-login');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsLogin);
});

test('changing user sets user', async () => {
  element.user = 'test user';
  await element.updateComplete;
  const link = element.shadowRoot.querySelector('a');
  assert.equal(link.textContent.trim(), 'LOGOUT');
});

test('a11y', () => {
  return auditA11y(element);
});
