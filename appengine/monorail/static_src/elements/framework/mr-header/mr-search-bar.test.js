// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';

import {MrSearchBar} from './mr-search-bar.js';
import {clientLoggerFake} from 'elements/shared/test-fakes.js';


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
      sinon.stub(element, '_navigateToList');
      element.clientLogger = clientLoggerFake;
    });

    afterEach(() => {
      element._navigateToList.restore();
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

      sinon.assert.calledOnce(element._navigateToList);
      sinon.assert.calledWith(element._navigateToList,
        {q: 'test query', can: '3'});
    });

    it('submit adds form values to url', async () => {
      await element.updateComplete;

      const form = element.shadowRoot.querySelector('form');

      form.q.value = 'test';
      form.can.value = '1';

      form.dispatchEvent(new Event('submit'));

      sinon.assert.calledOnce(element._navigateToList);
      sinon.assert.calledWith(element._navigateToList,
        {q: 'test', can: '1'});
    });

    it('submit only keeps kept query params', async () => {
      element.queryParams = {fakeParam: 'test', x: 'Status'};
      element.keptParams = ['x'];

      await element.updateComplete;

      const form = element.shadowRoot.querySelector('form');

      form.dispatchEvent(new Event('submit'));

      sinon.assert.calledOnce(element._navigateToList);
      sinon.assert.calledWith(element._navigateToList,
        {q: '', can: '2', x: 'Status'});
    });
  });
});
