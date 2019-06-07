// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsChipInput} from './chops-chip-input.js';
let element;

describe('mr-chip-input', () => {
  beforeEach(() => {
    element = document.createElement('chops-chip-input');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsChipInput);
  });

  it('adding values creates chips', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'world']);

    await element.updateComplete;

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 2);
    assert.deepEqual(
      element.getValues(), ['hello', 'world']);
  });

  it('immutable values render', async () => {
    await element.updateComplete;

    element.immutableValues = ['dont', 'change', 'me'];
    element.setValues(['hello', 'world']);

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');
    assert.equal(chips.length, 5);
    assert.include(chips[0].textContent, 'dont');
    assert.include(chips[1].textContent, 'change');
    assert.include(chips[2].textContent, 'me');
    assert.include(chips[3].textContent, 'hello');
    assert.include(chips[4].textContent, 'world');
    assert.deepEqual(
      element.getValues(), ['hello', 'world']);
  });

  it('chip input is focused when chip is focused', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'removeValue', 'world']);

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');

    chips[1].focus();
    element._changeFocus();
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('focused'));

    chips[1].blur();
    element._changeFocus();
    await element.updateComplete;

    assert.isFalse(element.hasAttribute('focused'));

    chips[0].focus();
    chips[2].focus();
    element._changeFocus();
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('focused'));
  });

  it('chip input is focused when add value input is focused', async () => {
    await element.updateComplete;

    const input = element.shadowRoot.querySelector('.add-value');

    input.focus();
    element._changeFocus();
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('focused'));

    input.blur();
    element._changeFocus();
    await element.updateComplete;

    assert.isFalse(element.hasAttribute('focused'));
  });

  it('clicking close button removes chip', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'removeValue', 'world']);

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');
    chips[1].clickIcon();

    await element.updateComplete;

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 2);
    assert.deepEqual(
      element.getValues(), ['hello', 'world']);
  });

  it('pressing left arrow key with chip focused changes focus', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'middle', 'world']);

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');
    chips[1].focus();

    element._interactWithChips({
      target: chips[1],
      key: 'ArrowLeft',
    });

    await element.updateComplete;

    // Chip in front is focused.
    assert.equal(element.shadowRoot.activeElement, chips[0]);

    element._interactWithChips({
      target: chips[0],
      key: 'ArrowLeft',
    });

    await element.updateComplete;

    // Focus not changed if already at the beginning of the input.
    assert.equal(element.shadowRoot.activeElement, chips[0]);

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 3);
    assert.deepEqual(
      element.getValues(), ['hello', 'middle', 'world']);
  });

  it('pressing right arrow key with chip focused changes focus', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'middle', 'world']);

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');
    chips[1].focus();

    element._interactWithChips({
      target: chips[1],
      key: 'ArrowRight',
    });

    await element.updateComplete;

    assert.equal(element.shadowRoot.activeElement, chips[2]);

    element._interactWithChips({
      target: chips[2],
      key: 'ArrowRight',
    });

    await element.updateComplete;

    // Moves to the input.
    assert.equal(element.shadowRoot.activeElement,
      element.shadowRoot.querySelector('.add-value'));

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 3);
    assert.deepEqual(
      element.getValues(), ['hello', 'middle', 'world']);
  });

  it('pressing left arrow key from input moves to last chip', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'middle', 'world']);

    await element.updateComplete;

    const input = element.shadowRoot.querySelector('.add-value');

    input.focus();

    element._navigateByKeyboard({
      target: input,
      key: 'ArrowLeft',
      stopPropagation: () => {},
    });

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');
    assert.equal(element.shadowRoot.activeElement, chips[2]);

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 3);
    assert.deepEqual(
      element.getValues(), ['hello', 'middle', 'world']);
  });

  it('pressing backspace from input deletes last chip', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'middle', 'world']);

    await element.updateComplete;

    const input = element.shadowRoot.querySelector('.add-value');

    input.focus();

    element._navigateByKeyboard({
      target: input,
      key: 'Backspace',
      stopPropagation: () => {},
    });

    await element.updateComplete;

    assert.equal(element.shadowRoot.activeElement, input);

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 2);
    assert.deepEqual(
      element.getValues(), ['hello', 'middle']);
  });

  it('pressing backspace with chip focused deletes chip', async () => {
    await element.updateComplete;

    element.setValues(['hello', 'removeValue', 'world']);

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');
    chips[1].focus();

    element._interactWithChips({
      target: chips[1],
      key: 'Backspace',
    });

    await element.updateComplete;

    // Chip in front is focused.
    assert.equal(element.shadowRoot.activeElement, chips[0]);

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 2);
    assert.deepEqual(
      element.getValues(), ['hello', 'world']);
  });

  it('pressing backspace on last chip focuses add value input', async () => {
    await element.updateComplete;

    element.setValues(['removeValue']);

    await element.updateComplete;

    const chips = element.shadowRoot.querySelectorAll('chops-chip');
    chips[0].focus();

    element._interactWithChips({
      target: chips[0],
      key: 'Backspace',
    });

    await element.updateComplete;

    // Input is focused.
    assert.equal(element.shadowRoot.activeElement,
      element.shadowRoot.querySelector('.add-value'));
    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 0);
    assert.deepEqual(
      element.getValues(), []);
  });

  it('input values with commas are turned into chips', async () => {
    await element.updateComplete;

    // Simulate user input.
    const input = element.shadowRoot.querySelector('.add-value');
    input.value = 'jaunty;jackalope,, jumps joyously!';

    // Because simulating keyboard input is difficult, we run element's onkeyup
    // handler directly.
    element._convertNewValuesToChips(input);

    await element.updateComplete;

    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 4);
    assert.deepEqual(
      element.getValues(), ['jaunty', 'jackalope', 'jumps', 'joyously!']);
  });

  it('getValues finds trailing non-chip value', async () => {
    await element.updateComplete;

    const input = element.shadowRoot.querySelector('.add-value');
    element.values = ['it', 'chip2'];

    await element.updateComplete;
    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 2);

    input.value = 'blah-no-delimiter';

    await element.updateComplete;
    assert.equal(element.shadowRoot.querySelectorAll('chops-chip').length, 2);

    assert.deepEqual(
      element.getValues(), ['it', 'chip2', 'blah-no-delimiter']);
  });

  it('undo restores old values', async () => {
    await element.updateComplete;

    element.setValues(['test', 'hello']);

    await element.updateComplete;
    assert.deepEqual(element.values, ['test', 'hello']);

    element.setValues(['test', 'hello', 'newValue']);

    await element.updateComplete;
    assert.deepEqual(element.values, ['test', 'hello', 'newValue']);

    element.undo();

    await element.updateComplete;
    assert.deepEqual(element.values, ['test', 'hello']);
  });

  it('undo stack caps at max size', async () => {
    await element.updateComplete;

    element.values = ['four'];
    element.undoLimit = 3;
    element.undoStack = [['one'], ['two'], ['three']];

    element.setValues(['five']);

    assert.deepEqual(element.undoStack, [['two'], ['three'], ['four']]);
  });
});
