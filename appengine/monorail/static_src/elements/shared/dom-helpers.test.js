// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {isTextInput} from './dom-helpers.js';

describe('isTextInput', () => {
  it('returns true for select', () => {
    const element = document.createElement('select');
    assert.isTrue(isTextInput(element));
  });

  it('returns true for input tags that take text input', () => {
    const element = document.createElement('input');
    assert.isTrue(isTextInput(element));

    element.type = 'text';
    assert.isTrue(isTextInput(element));

    element.type = 'password';
    assert.isTrue(isTextInput(element));

    element.type = 'number';
    assert.isTrue(isTextInput(element));

    element.type = 'date';
    assert.isTrue(isTextInput(element));
  });

  it('returns false for input tags without text input', () => {
    const element = document.createElement('input');

    element.type = 'button';
    assert.isFalse(isTextInput(element));

    element.type = 'submit';
    assert.isFalse(isTextInput(element));

    element.type = 'checkbox';
    assert.isFalse(isTextInput(element));

    element.type = 'radio';
    assert.isFalse(isTextInput(element));
  });

  it('returns true for textarea', () => {
    const element = document.createElement('textarea');
    assert.isTrue(isTextInput(element));
  });

  it('returns true for contenteditable', () => {
    const element = document.createElement('div');
    element.contentEditable = 'true';
    assert.isTrue(isTextInput(element));

    element.contentEditable = 'false';
    assert.isFalse(isTextInput(element));
  });

  it('returns false for non-input', () => {
    assert.isFalse(isTextInput(document.createElement('div')));
    assert.isFalse(isTextInput(document.createElement('table')));
    assert.isFalse(isTextInput(document.createElement('tr')));
    assert.isFalse(isTextInput(document.createElement('td')));
    assert.isFalse(isTextInput(document.createElement('href')));
    assert.isFalse(isTextInput(document.createElement('random-elment')));
    assert.isFalse(isTextInput(document.createElement('p')));
  });
});
