// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import {MrChoiceButtons} from './mr-choice-buttons';

let element;

describe('mr-choice-buttons', () => {
  beforeEach(() => {
    element = document.createElement('mr-choice-buttons');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrChoiceButtons);
  });
});
