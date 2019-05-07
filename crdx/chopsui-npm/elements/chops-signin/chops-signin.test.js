// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsSignin} from './index.js';
import {auditA11y} from '../../test-helpers';

let element;

suite('chops-signin');

beforeEach(() => {
  element = document.createElement('chops-signin');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.equal(element.constructor.name, 'ChopsSignin');
});

test('lack of clientId results in error message', async () => {
  await element.updateComplete;
  assert.isDefined(element.errorMsg);
});

test('clientId set, no error message', async () => {
  element.setAttribute('client-id', 'foobar');
  await element.updateComplete;
  assert.isUndefined(element.errorMsg);
});

test('update user', () => {
  element.onUserUpdate_();
  assert.equal(element.title, 'Sign in with Google');
});

test('a11y', () => {
  return auditA11y(element);
});
