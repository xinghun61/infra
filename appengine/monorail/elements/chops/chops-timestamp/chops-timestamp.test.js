// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsTimestamp} from './chops-timestamp.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;

suite('chops-timestamp');

beforeEach(() => {
  element = document.createElement('chops-timestamp');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsTimestamp);
});

test('changing timestamp changes date', () => {
  element.dateFormat = `ddd D MMM 'YY, h:mm a [LSKJFLSKDJFLKSDFJ]`;

  element.timestamp = '1548808276';

  flush();

  assert.include(element.shadowRoot.textContent,
    `Tue 29 Jan '19, 4:31 pm LSKJFLSKDJFLKSDFJ`);
});
