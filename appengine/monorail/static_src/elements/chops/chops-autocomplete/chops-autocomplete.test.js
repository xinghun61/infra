// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import {assert} from 'chai';
import {ChopsAutocomplete} from './chops-autocomplete.js';

let element;
let input;

describe('chops-autocomplete', () => {
  beforeEach(() => {
    element = document.createElement('chops-autocomplete');
    document.body.appendChild(element);

    input = document.createElement('input');
    input.id = 'autocomplete-input';
    document.body.appendChild(input);

    element.for = 'autocomplete-input';
  });

  afterEach(() => {
    document.body.removeChild(element);
    document.body.removeChild(input);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsAutocomplete);
  });

  it('registers child input', async () => {
    await element.updateComplete;

    assert.isNotNull(element._forRef);
    assert.equal(element._forRef.tagName.toUpperCase(), 'INPUT');
  });

  it('completeValue sets input value', async () => {
    await element.updateComplete;

    element.completeValue('test');
    assert.equal(input.value, 'test');

    element.completeValue('again');
    assert.equal(input.value, 'again');
  });

  it('completeValue can run a custom replacer', async () => {
    element.replacer = (input, value) => input.value = value + ',';
    await element.updateComplete;

    element.completeValue('trailing');
    assert.equal(input.value, 'trailing,');

    element.completeValue('comma');
    assert.equal(input.value, 'comma,');
  });

  it('completions render', async () => {
    element.completions = ['hello', 'world'];
    element.docDict = {'hello': 'well hello there'};
    await element.updateComplete;

    const completions = element.querySelectorAll('.completion');
    const docstrings = element.querySelectorAll('.docstring');

    assert.equal(completions.length, 2);
    assert.equal(docstrings.length, 2);

    assert.include(completions[0].textContent, 'hello');
    assert.include(completions[1].textContent, 'world');

    assert.include(docstrings[0].textContent, 'well hello there');
    assert.include(docstrings[1].textContent, '');
  });

  it('completions bold matched section when rendering', async () => {
    element.completions = ['hello-world'];
    element._prefix = 'wor';
    element._matchDict = {
      'hello-world': {'index': 6},
    };

    await element.updateComplete;

    const completion = element.querySelector('.completion');

    assert.include(completion.textContent, 'hello-world');

    assert.equal(completion.querySelector('b').textContent.trim(), 'wor');
  });


  it('showCompletions populates completions with matches', async () => {
    element.strings = [
      'test-one',
      'test-two',
      'ignore',
      'hello',
      'woah-test',
      'i-am-a-tester',
    ];
    input.value = 'test';
    await element.updateComplete;

    element.showCompletions();

    assert.deepEqual(element.completions, [
      'test-one',
      'test-two',
      'woah-test',
      'i-am-a-tester',
    ]);
  });

  it('showCompletions matches docs', async () => {
    element.strings = [
      'hello',
      'world',
      'no-op',
    ];
    element.docDict = {'world': 'this is a test'};
    input.value = 'test';
    await element.updateComplete;

    element.showCompletions();

    assert.deepEqual(element.completions, [
      'world',
    ]);
  });

  it('showCompletions caps completions at max', async () => {
    element.max = 2;
    element.strings = [
      'test-one',
      'test-two',
      'ignore',
      'hello',
      'woah-test',
      'i-am-a-tester',
    ];
    input.value = 'test';
    await element.updateComplete;

    element.showCompletions();

    assert.deepEqual(element.completions, [
      'test-one',
      'test-two',
    ]);
  });

  it('hideCompletions hides completions', async () => {
    element.completions = [
      'test-one',
      'test-two',
    ];

    await element.updateComplete;

    const completionTable = element.querySelector('table');
    assert.isFalse(completionTable.hidden);

    element.hideCompletions();

    await element.updateComplete;

    assert.isTrue(completionTable.hidden);
  });

  it('clicking completion completes it', async () => {
    element.completions = [
      'test-one',
      'test-two',
      'click me!',
      'test',
    ];

    await element.updateComplete;

    const completions = element.querySelectorAll('tr');

    assert.equal(input.value, '');

    // Note: the click() event can only trigger click events, not mousedown
    // events, so we are instead manually running the event handler.
    element._clickCompletion({
      preventDefault: sinon.stub(),
      currentTarget: completions[2],
    });

    assert.equal(input.value, 'click me!');
  });

  it('completion is scrolled into view when outside viewport', async () => {
    element.completions = [
      'i',
      'am',
      'an option',
    ];
    element._selectedIndex = 0;
    element.id = 'chops-autocomplete-1';

    await element.updateComplete;

    const container = element.querySelector('tbody');
    const completion = container.querySelector('tr');
    const completionHeight = completion.offsetHeight;
    // Make the table one row tall.
    container.style.height = `${completionHeight}px`;

    element._selectedIndex = 1;
    await element.updateComplete;

    assert.equal(container.scrollTop, completionHeight);

    element._selectedIndex = 2;
    await element.updateComplete;

    assert.equal(container.scrollTop, completionHeight * 2);

    element._selectedIndex = 0;
    await element.updateComplete;

    assert.equal(container.scrollTop, 0);
  });

  it('aria-activedescendant set based on selected option', async () => {
    element.completions = [
      'i',
      'am',
      'an option',
    ];
    element._selectedIndex = 1;
    element.id = 'chops-autocomplete-1';

    await element.updateComplete;

    assert.equal(input.getAttribute('aria-activedescendant'),
        'chops-autocomplete-1-option-1');
  });

  it('hovering over a completion selects it', async () => {
    element.completions = [
      'hover',
      'over',
      'me',
    ];

    await element.updateComplete;

    const completions = element.querySelectorAll('tr');

    element._hoverCompletion({
      currentTarget: completions[2],
    });

    assert.equal(element._selectedIndex, 2);

    element._hoverCompletion({
      currentTarget: completions[1],
    });

    assert.equal(element._selectedIndex, 1);
  });

  it('ArrowDown moves through completions', async () => {
    element.completions = [
      'move',
      'down',
      'me',
    ];

    element._selectedIndex = 0;

    await element.updateComplete;

    const preventDefault = sinon.stub();

    element._navigateCompletions({preventDefault, key: 'ArrowDown'});
    assert.equal(element._selectedIndex, 1);

    element._navigateCompletions({preventDefault, key: 'ArrowDown'});
    assert.equal(element._selectedIndex, 2);

    // Wrap around.
    element._navigateCompletions({preventDefault, key: 'ArrowDown'});
    assert.equal(element._selectedIndex, 0);

    sinon.assert.callCount(preventDefault, 3);
  });

  it('ArrowUp moves through completions', async () => {
    element.completions = [
      'move',
      'up',
      'me',
    ];

    element._selectedIndex = 0;

    await element.updateComplete;

    const preventDefault = sinon.stub();

    // Wrap around.
    element._navigateCompletions({preventDefault, key: 'ArrowUp'});
    assert.equal(element._selectedIndex, 2);

    element._navigateCompletions({preventDefault, key: 'ArrowUp'});
    assert.equal(element._selectedIndex, 1);

    element._navigateCompletions({preventDefault, key: 'ArrowUp'});
    assert.equal(element._selectedIndex, 0);

    sinon.assert.callCount(preventDefault, 3);
  });

  it('Enter completes with selected completion', async () => {
    element.completions = [
      'hello',
      'pick me',
      'world',
    ];

    element._selectedIndex = 1;

    await element.updateComplete;

    const preventDefault = sinon.stub();

    element._navigateCompletions({preventDefault, key: 'Enter'});

    assert.equal(input.value, 'pick me');
    sinon.assert.callCount(preventDefault, 1);
  });

  it('Escape hides completions', async () => {
    element.completions = [
      'hide',
      'me',
    ];

    await element.updateComplete;

    const preventDefault = sinon.stub();
    element._navigateCompletions({preventDefault, key: 'Escape'});

    sinon.assert.callCount(preventDefault, 1);

    await element.updateComplete;

    assert.equal(element.completions.length, 0);
  });
});
