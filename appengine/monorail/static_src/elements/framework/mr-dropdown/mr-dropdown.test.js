// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrDropdown, SCREENREADER_ATTRIBUTE_ERROR} from './mr-dropdown.js';
import sinon from 'sinon';

let element;
let randomButton;

describe('mr-dropdown', () => {
  beforeEach(() => {
    element = document.createElement('mr-dropdown');
    document.body.appendChild(element);
    element.label = 'new dropdown';

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

  it('warns users about accessibility when no label or text', async () => {
    element.label = 'ok';
    sinon.spy(console, 'error');

    await element.updateComplete;
    sinon.assert.notCalled(console.error);

    element.label = undefined;

    await element.updateComplete;
    sinon.assert.calledWith(console.error, SCREENREADER_ATTRIBUTE_ERROR);

    console.error.restore();
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

  describe('nested dropdown menus', () => {
    beforeEach(() => {
      element.items = [
        {
          text: 'test',
          items: [
            {text: 'item 1'},
            {text: 'item 2'},
            {text: 'item 3'},
          ],
        },
      ];

      element.open();
    });

    it('nested dropdown menu renders', async () => {
      await element.updateComplete;

      const nestedDropdown = element.shadowRoot.querySelector('mr-dropdown');

      assert.equal(nestedDropdown.text, 'test');
      assert.deepEqual(nestedDropdown.items, [
        {text: 'item 1'},
        {text: 'item 2'},
        {text: 'item 3'},
      ]);
    });

    it('clicking nested item with handler calls handler', async () => {
      const handler = sinon.stub();
      element.items = [{
        text: 'test',
        items: [
          {text: 'item 1'},
          {
            text: 'item with handler',
            handler,
          },
        ],
      }];

      await element.updateComplete;

      const nestedDropdown = element.shadowRoot.querySelector('mr-dropdown');

      nestedDropdown.open();
      await element.updateComplete;

      // Clicking an unrelated nested item shouldn't call the handler.
      nestedDropdown.clickItem(0);
      // Nor should clicking the parent item call the handler.
      element.clickItem(0);
      sinon.assert.notCalled(handler);

      element.open();
      nestedDropdown.open();
      await element.updateComplete;

      nestedDropdown.clickItem(1);
      sinon.assert.calledOnce(handler);
    });

    it('clicking nested dropdown menu toggles nested menu', async () => {
      await element.updateComplete;

      const nestedDropdown = element.shadowRoot.querySelector('mr-dropdown');
      const nestedAnchor = nestedDropdown.shadowRoot.querySelector('.anchor');

      assert.isTrue(element.opened);
      assert.isFalse(nestedDropdown.opened);

      nestedAnchor.click();
      await element.updateComplete;

      assert.isTrue(element.opened);
      assert.isTrue(nestedDropdown.opened);

      nestedAnchor.click();
      await element.updateComplete;

      assert.isTrue(element.opened);
      assert.isFalse(nestedDropdown.opened);
    });
  });
});
