/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import {expect, assert} from 'chai';
import {ChopsDialog} from './chops-dialog.js';

let element;

suite('chops-dialog');

beforeEach(() => {
  element = document.createElement('chops-dialog');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsDialog);
});

test('chops-dialog is visible when open', () => {
  element.opened = false;
  expect(element).be.hidden;

  element.opened = true;

  expect(element).be.visible;
});
