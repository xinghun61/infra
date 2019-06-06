// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsInput} from './chops-input.js';
import {auditA11y} from '../../test-helpers';

let element;

suite('chops-input');

beforeEach(() => {
  element = document.createElement('chops-input');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsInput);
});

test('clickFocuses', async () => {
  assert.isFalse(element.focused);
  element.click();
  await element.updateComplete;
  assert.isTrue(element.focused);
});

test('keyup', async () => {
  await element.updateComplete;
  element.native.value = 'hello';
  element.native.dispatchEvent(new CustomEvent('keyup'));
  assert.strictEqual(element.value, element.native.value);
});

test('a11y', () => {
  return auditA11y(element);
});
