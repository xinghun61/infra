// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsSigninAware} from './chops-signin-aware.js';
import {auditA11y} from '../../test-helpers';

let element;

suite('chops-signin-aware');

beforeEach(() => {
  element = document.createElement('chops-signin-aware');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsSigninAware);
});

test('a11y', () => {
  return auditA11y(element);
});
