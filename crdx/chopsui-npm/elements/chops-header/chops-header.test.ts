// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import { assert } from 'chai';
import { ChopsHeader } from './chops-header.js';
import { auditA11y } from '../../test-helpers/test-helpers.js';

let element;

suite('chops-header');

beforeEach(() => {
  element = document.createElement('chops-header');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsHeader);
});

test('changing appTitle sets title', async () => {
  element.appTitle = 'test';
  await element.updateComplete;
  const title = element.shadowRoot.querySelector('#headerTitleTextMain');
  assert.equal(title.textContent.trim(), 'test');
});

test('a11y', () => {
  return auditA11y(element);
});
