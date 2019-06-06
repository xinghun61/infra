// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsTextarea} from './chops-textarea.js';
import {auditA11y} from '../../test-helpers';

let element;

suite('chops-textarea');

beforeEach(() => {
  element = document.createElement('chops-textarea');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsTextarea);
});

test('a11y', () => {
  return auditA11y(element);
});
