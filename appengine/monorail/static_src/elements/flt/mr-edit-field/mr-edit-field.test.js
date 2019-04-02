// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditField} from './mr-edit-field.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {fieldTypes} from '../../shared/field-types.js';


let element;

suite('mr-edit-field', () => {
  setup(() => {
    element = document.createElement('mr-edit-field');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrEditField);
  });

  test('reset input value', () => {
    flush();

    // Simulate user input.
    element.shadowRoot.querySelector('#editInput').value = 'jackalope';
    element.initialValues = [];
    assert.equal(element.getValue(), '');
  });

  test('input updates when initialValues change', () => {
    flush();

    element.initialValues = ['hello'];
    assert.equal(element.getValue(), 'hello');
  });

  test('initial value does not change after setValue', () => {
    flush();

    element.initialValues = ['hello'];
    element.setValue('world');
    assert.deepEqual(element.initialValues, ['hello']);
  });

  test('input updates when setValue is called', () => {
    flush();
    element.initialValues = ['hello'];
    element.setValue('world');
    assert.equal(element.getValue(), 'world');
  });

  test('initial value does not change after user input', () => {
    flush();
    element.initialValues = ['hello'];
    // Simulate user input.
    element.shadowRoot.querySelector('#editInput').value = 'jackalope';
    assert.deepEqual(element.initialValues, ['hello']);
  });

  test('get value after user input', () => {
    element.initialValues = ['hello'];
    // Simulate user input.
    element.shadowRoot.querySelector('#editInput').value = 'jackalope';
    assert.equal(element.getValue(), 'jackalope');
  });

  test('input value was added', () => {
    flush();
    // Simulate user input.
    element.shadowRoot.querySelector('#editInput').value = 'jackalope';
    assert.deepEqual(element.getValuesAdded(), ['jackalope']);
  });

  test('input value was removed', () => {
    flush();
    element.initialValues = ['hello'];
    // Simulate user input.
    element.shadowRoot.querySelector('#editInput').value = '';
    assert.deepEqual(element.getValuesRemoved(), ['hello']);
  });

  test('input value was changed', () => {
    flush();
    element.initialValues = ['hello'];
    // Simulate user input.
    element.shadowRoot.querySelector('#editInput').value = 'world';
    assert.deepEqual(element.getValuesAdded(), ['world']);
  });

  test('edit select updates value when initialValues change', () => {
    element.multi = false;
    element.type = fieldTypes.ENUM_TYPE;

    element.options = [
      {optionName: 'hello'},
      {optionName: 'jackalope'},
      {optionName: 'text'},
    ];

    flush();

    element.initialValues = ['hello'];
    assert.equal(element.getValue(), 'hello');

    // Simulate user input.
    element.shadowRoot.querySelector('#editSelect').value = 'jackalope';
    // User input should not be overridden by the initialValue variable.
    assert.equal(element.getValue(), 'jackalope');
    // Initial values should not change based on user input.
    assert.deepEqual(element.initialValues, ['hello']);

    element.initialValues = ['text'];
    assert.equal(element.getValue(), 'text');

    element.initialValues = [];
    assert.deepEqual(element.getValue(), '');
  });

  test('edit enum updates value when initialValues change', () => {
    element.multi = true;
    element.type = fieldTypes.ENUM_TYPE;
    element.options = [
      {optionName: 'hello'},
      {optionName: 'world'},
      {optionName: 'fake'},
    ];

    flush();

    element.initialValues = ['hello'];
    assert.deepEqual(element.getValues(), ['hello']);

    // User checks all boxes.
    element.shadowRoot.querySelector('mr-multi-checkbox').shadowRoot
      .querySelectorAll('input').forEach(
        (checkbox) => {
          checkbox.checked = true;
        }
      );
    // User input should not be overridden by the initialValue variable.
    assert.deepEqual(element.getValues(), ['hello', 'world', 'fake']);
    // Initial values should not change based on user input.
    assert.deepEqual(element.initialValues, ['hello']);

    element.initialValues = ['hello', 'world'];
    assert.deepEqual(element.getValues(), ['hello', 'world']);
  });
});
