// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';

import {MrSearchBar} from './mr-search-bar.js';
import {clientLoggerFake} from 'shared/test-fakes.js';


window.CS_env = {
  token: 'foo-token',
};

let element;

describe('mr-search-bar', () => {
  beforeEach(() => {
    element = document.createElement('mr-search-bar');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrSearchBar);
  });

  it('render user saved queries', async () => {
    element.userDisplayName = 'test@user.com';
    element.userSavedQueries = [
      {name: 'test query', queryId: 101},
      {name: 'hello world', queryId: 202},
    ];

    await element.updateComplete;

    const queryOptions = element.shadowRoot.querySelectorAll(
        '.user-query');

    assert.equal(queryOptions.length, 2);

    assert.equal(queryOptions[0].value, '101');
    assert.equal(queryOptions[0].textContent, 'test query');

    assert.equal(queryOptions[1].value, '202');
    assert.equal(queryOptions[1].textContent, 'hello world');
  });

  it('render project saved queries', async () => {
    element.userDisplayName = 'test@user.com';
    element.projectSavedQueries = [
      {name: 'test query', queryId: 101},
      {name: 'hello world', queryId: 202},
    ];

    await element.updateComplete;

    const queryOptions = element.shadowRoot.querySelectorAll(
        '.project-query');

    assert.equal(queryOptions.length, 2);

    assert.equal(queryOptions[0].value, '101');
    assert.equal(queryOptions[0].textContent, 'test query');

    assert.equal(queryOptions[1].value, '202');
    assert.equal(queryOptions[1].textContent, 'hello world');
  });

  it('spell check is off for search bar', async () => {
    await element.updateComplete;
    const searchElement = element.shadowRoot.querySelector('#searchq');
    assert.equal(searchElement.getAttribute('spellcheck'), 'false');
  });

  describe('search form submit', () => {
    beforeEach(() => {
      element.clientLogger = clientLoggerFake();

      element._page = sinon.stub();
      sinon.stub(window, 'open');

      element.projectName = 'chromium';
    });

    afterEach(() => {
      window.open.restore();
    });

    it('submit prevents default', async () => {
      await element.updateComplete;

      const form = element.shadowRoot.querySelector('form');

      // Note: HTMLFormElement's submit function does not run submit handlers
      // but clicking a submit buttons programmatically works.
      const event = new Event('submit');
      sinon.stub(event, 'preventDefault');
      form.dispatchEvent(event);

      sinon.assert.calledOnce(event.preventDefault);
    });

    it('submit uses default values when no form changes', async () => {
      element.initialValue = 'test query';
      element.defaultCan = '3';

      await element.updateComplete;

      const form = element.shadowRoot.querySelector('form');

      form.dispatchEvent(new Event('submit'));

      sinon.assert.calledOnce(element._page);
      sinon.assert.calledWith(element._page,
          '/p/chromium/issues/list?q=test%20query&can=3');
    });

    it('submit adds form values to url', async () => {
      await element.updateComplete;

      const form = element.shadowRoot.querySelector('form');

      form.q.value = 'test';
      form.can.value = '1';

      form.dispatchEvent(new Event('submit'));

      sinon.assert.calledOnce(element._page);
      sinon.assert.calledWith(element._page,
          '/p/chromium/issues/list?q=test&can=1');
    });

    it('submit only keeps kept query params', async () => {
      element.queryParams = {fakeParam: 'test', x: 'Status'};
      element.keptParams = ['x'];

      await element.updateComplete;

      const form = element.shadowRoot.querySelector('form');

      form.dispatchEvent(new Event('submit'));

      sinon.assert.calledOnce(element._page);
      sinon.assert.calledWith(element._page,
          '/p/chromium/issues/list?x=Status&q=&can=2');
    });

    it('shift+enter opens search in new tab', async () => {
      await element.updateComplete;

      const form = element.shadowRoot.querySelector('form');

      form.q.value = 'test';
      form.can.value = '1';

      // Dispatch event from an input in the form.
      form.q.dispatchEvent(new KeyboardEvent('keypress',
          {key: 'Enter', shiftKey: true, bubbles: true}));

      sinon.assert.calledOnce(window.open);
      sinon.assert.calledWith(window.open,
          '/p/chromium/issues/list?q=test&can=1', '_blank', 'noopener');
    });
  });
});
