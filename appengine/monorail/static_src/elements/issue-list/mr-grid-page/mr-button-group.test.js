// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import {MrButtonGroup} from './mr-button-group';

let element;

describe('mr-button-group', () => {
  beforeEach(() => {
    element = document.createElement('mr-button-group');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrButtonGroup);
  });
});
