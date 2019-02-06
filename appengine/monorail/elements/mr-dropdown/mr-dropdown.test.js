// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrDropdown} from './mr-dropdown.js';

let element;
let randomButton;

suite('mr-dropdown');

beforeEach(() => {
  element = document.createElement('mr-dropdown');
  document.body.appendChild(element);

  randomButton = document.createElement('button');
  document.body.appendChild(randomButton);
});

afterEach(() => {
  document.body.removeChild(element);
  document.body.removeChild(randomButton);
});

test('initializes', () => {
  assert.instanceOf(element, MrDropdown);
});

test('toggle changes opened state', () => {
  element.open();
  assert.isTrue(element.opened);

  element.close();
  assert.isFalse(element.opened);

  element.toggle();
  assert.isTrue(element.opened);

  element.toggle();
  assert.isFalse(element.opened);

  element.toggle();
  element.toggle();
  assert.isFalse(element.opened);
});


test('clicking outside element closes menu', () => {
  element.open();
  assert.isTrue(element.opened);

  randomButton.click();

  assert.isFalse(element.opened);
});
