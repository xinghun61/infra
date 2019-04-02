// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrMultiInput} from './mr-multi-input.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {fieldTypes} from '../../shared/field-types.js';

let element;

suite('mr-multi-input', () => {
  setup(() => {
    element = document.createElement('mr-multi-input');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrMultiInput);
  });

  test('input updates when initialValues change', () => {
    element.initialValues = ['hello', 'world'];
    flush();
    assert.deepEqual(element.getValues(), ['hello', 'world']);
  });

  test('input updates when setValues is called', () => {
    element.initialValues = ['hello', 'world'];
    element.setValues(['jaunty', 'jackalope', 'jumps', 'joyously']);
    flush();
    assert.deepEqual(
      element.getValues(), ['jaunty', 'jackalope', 'jumps', 'joyously']);
  });

  test('initial value does not change after user input', () => {
    element.initialValues = ['hello'];
    flush();
    // Simulate user input.
    element.shadowRoot.querySelector('#multi1').value = 'heron';
    assert.deepEqual(element.initialValues, ['hello']);
  });

  test('resetting input to initial value works', () => {
    element.initialValues = [];
    flush();
    // Simulate user input.
    element.shadowRoot.querySelector('#multi0').value = 'heron';
    element.reset();
    flush();

    assert.deepEqual(element.initialValues, []);
    assert.equal(element.shadowRoot.querySelector('#multi0').value.trim(), '');
  });

  test('get value after user input', () => {
    element.initialValues = ['hello'];
    flush();
    // Simulate user input.
    element.shadowRoot.querySelector('#multi1').value = 'heron';
    assert.deepEqual(element.getValues(), ['hello', 'heron']);
  });

  test('input value was added', () => {
    flush();
    // Simulate user input.
    element.shadowRoot.querySelector('#multi0').value = 'jackalope';
    assert.deepEqual(element.getValues(), ['jackalope']);
  });

  test('input value was removed', () => {
    element.initialValues = ['hello'];
    flush();
    // Simulate user input.
    element.shadowRoot.querySelector('#multi0').value = '';
    assert.deepEqual(element.getValues(), []);
  });

  test('input value was changed', () => {
    element.initialValues = ['hello'];
    flush();
    // Simulate user input.
    element.shadowRoot.querySelector('#multi0').value = 'world';
    assert.deepEqual(element.getValues(), ['world']);
  });

  test('input value has commas', () => {
    flush();
    element.acType = 'member';

    // Simulate user input.
    const input = element.shadowRoot.querySelector('#multi0');
    input.value = 'jaunty;jackalope,, jumps joyously!';
    element._postProcess();

    flush();

    // Input is split on several input fields.
    assert.deepEqual(
      Array.from(element.shadowRoot.querySelectorAll('input')).map(
        (input) => input.value),
      ['jaunty', 'jackalope', 'jumps', 'joyously!', '']);

    // values are updated
    assert.deepEqual(
      element.getValues(), ['jaunty', 'jackalope', 'jumps', 'joyously!']);
  });

  test('input value has commas but is not delimitable', () => {
    flush();
    element.type = fieldTypes.STR_TYPE;

    // Simulate user input.
    const input = element.shadowRoot.querySelector('#multi0');
    input.value = 'jaunty;jackalope,, jumps joyously!';

    element._postProcess();
    flush();

    // Input is not split into several input fields.
    assert.deepEqual(
      Array.from(element.shadowRoot.querySelectorAll('input')).map(
        (input) => input.value),
      ['jaunty;jackalope,, jumps joyously!', '']);
    assert.deepEqual(
      element.getValues(), ['jaunty;jackalope,, jumps joyously!']);

    element.type = fieldTypes.DATE_TYPE;
    element._postProcess();
    flush();

    // Input is not split into several input fields.
    assert.deepEqual(
      Array.from(element.shadowRoot.querySelectorAll('input')).map(
        (input) => input.value),
      ['jaunty;jackalope,, jumps joyously!', '']);
    assert.deepEqual(
      element.getValues(), ['jaunty;jackalope,, jumps joyously!']);

    element.type = fieldTypes.URL_TYPE;
    element._postProcess();
    flush();

    // Input is not split into several input fields.
    assert.deepEqual(
      Array.from(element.shadowRoot.querySelectorAll('input')).map(
        (input) => input.value),
      ['jaunty;jackalope,, jumps joyously!', '']);
    assert.deepEqual(
      element.getValues(), ['jaunty;jackalope,, jumps joyously!']);
  });
});
