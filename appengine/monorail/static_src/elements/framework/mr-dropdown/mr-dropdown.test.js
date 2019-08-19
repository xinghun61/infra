// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrDropdown} from './mr-dropdown.js';
import sinon from 'sinon';

let element;
let randomButton;

describe('mr-dropdown', () => {
  beforeEach(() => {
    element = document.createElement('mr-dropdown');
    document.body.appendChild(element);

    randomButton = document.createElement('button');
    document.body.appendChild(randomButton);
  });

  afterEach(() => {
    document.body.removeChild(element);
    document.body.removeChild(randomButton);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrDropdown);
  });

  it('toggle changes opened state', () => {
    element.open();
    assert.isTrue(element.opened);

    element.close();
    assert.isFalse(element.opened);

    element.toggle();
    assert.isTrue(element.opened);

    element.toggle();
    assert.isFalse(element.opened);

    element.toggle();
    element.toggle();
    assert.isFalse(element.opened);
  });


  it('clicking outside element closes menu', () => {
    element.open();
    assert.isTrue(element.opened);

    randomButton.click();

    assert.isFalse(element.opened);
  });

  it('icon hidden when undefined', async () => {
    element.items = [
      {text: 'test'},
    ];

    await element.updateComplete;

    const icon = element.shadowRoot.querySelector(
        '.menu-item > .material-icons');

    assert.isTrue(icon.hidden);
  });

  it('icon shown when defined, even as empty string', async () => {
    element.items = [
      {text: 'test', icon: ''},
    ];

    await element.updateComplete;

    const icon = element.shadowRoot.querySelector(
        '.menu-item > .material-icons');

    assert.isFalse(icon.hidden);
    assert.equal(icon.textContent.trim(), '');
  });

  it('icon shown when set to material icon', async () => {
    element.items = [
      {text: 'test', icon: 'check'},
    ];

    await element.updateComplete;

    const icon = element.shadowRoot.querySelector(
        '.menu-item > .material-icons');

    assert.isFalse(icon.hidden);
    assert.equal(icon.textContent.trim(), 'check');
  });

  it('items with handlers are handled', async () => {
    const handler1 = sinon.spy();
    const handler2 = sinon.spy();
    const handler3 = sinon.spy();

    element.items = [
      {
        url: '#',
        text: 'blah',
        handler: handler1,
      },
      {
        url: '#',
        text: 'rutabaga noop',
        handler: handler2,
      },
      {
        url: '#',
        text: 'click me please',
        handler: handler3,
      },
    ];

    element.open();

    await element.updateComplete;

    element.clickItem(0);

    assert.isTrue(handler1.calledOnce);
    assert.isFalse(handler2.called);
    assert.isFalse(handler3.called);

    element.clickItem(2);

    assert.isTrue(handler1.calledOnce);
    assert.isFalse(handler2.called);
    assert.isTrue(handler3.calledOnce);
  });
});
