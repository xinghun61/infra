/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import {assert} from 'chai';
import {ChopsHeader} from './chops-header.js';

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
