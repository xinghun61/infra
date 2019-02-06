// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert, expect} from 'chai';
import {MrUserLink} from './mr-user-link.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;

suite('mr-user-link');

beforeEach(() => {
  element = document.createElement('mr-user-link');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, MrUserLink);
});


test('no link when no userId', () => {
  element.displayName = 'Hello world';
  flush();

  expect(element.$.userLink).be.hidden;
  expect(element.$.userText).be.visible;
  assert.equal(element.$.userText.textContent.trim(), 'Hello world');
});
