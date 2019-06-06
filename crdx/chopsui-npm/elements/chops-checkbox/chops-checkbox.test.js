// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsCheckbox} from './chops-checkbox.js';
import {auditA11y} from '../../test-helpers';

let element;

suite('chops-checkbox');

beforeEach(() => {
  element = document.createElement('chops-checkbox');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsCheckbox);
});

test('click', async () => {
  await element.updateComplete;
  assert.isFalse(element.checked);
  let changeEvent;
  element.addEventListener('change', (event) => {
    changeEvent = event;
  });
  element.click();
  await element.updateComplete;
  assert.isTrue(element.checked);
  assert.isDefined(changeEvent);
  changeEvent = undefined;
  element.click();
  await element.updateComplete;
  assert.isFalse(element.checked);
  assert.isDefined(changeEvent);
});

test('a11y', () => {
  return auditA11y(element);
});
