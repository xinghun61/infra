// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsRadio} from './chops-radio.js';
import {auditA11y} from '../../test-helpers';

let element;

suite('chops-radio');

beforeEach(() => {
  element = document.createElement('chops-radio');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsRadio);
});

test('a11y', () => {
  return auditA11y(element);
});
