// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrStarButton} from './mr-star-button.js';
import {issueRefToString} from '../../shared/converters.js';
import sinon from 'sinon';


let element;

describe('mr-star-button', () => {
  beforeEach(() => {
    element = document.createElement('mr-star-button');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrStarButton);
  });

  it('clicking star toggles star', async () => {
    sinon.spy(element, 'toggleStar');
    element._isLoggedIn = true;

    await element.updateComplete;

    assert.isTrue(element._canStar);
    assert.isTrue(element.toggleStar.notCalled);

    element.shadowRoot.querySelector('button').click();

    assert.isTrue(element.toggleStar.called);

    element.toggleStar.restore();
  });

  it('starring is disabled when user is not logged in', async () => {
    element._isLoggedIn = false;

    await element.updateComplete;

    const star = element.shadowRoot.querySelector('button');
    assert.isTrue(star.disabled);
  });

  it('_isStarring true only when issue ref is being starred', async () => {
    element._starringIssues = new Map([['chromium:22', {requesting: true}]]);
    element.issueRef = {projectName: 'chromium', localId: 5};

    assert.isFalse(element._isStarring);

    element.issueRef = {projectName: 'chromium', localId: 22};

    assert.isTrue(element._isStarring);

    element._starringIssues = new Map([['chromium:22', {requesting: false}]]);

    assert.isFalse(element._isStarring);
  });

  it('starring is disabled when _isStarring true', async () => {
    element._isLoggedIn = true;
    sinon.stub(element, '_isStarring').get(() => true);

    await element.updateComplete;

    const star = element.shadowRoot.querySelector('button');
    assert.isTrue(star.disabled);
  });

  it('starring is disabled when _fetchingIsStarred true', async () => {
    element._isLoggedIn = true;
    element._fetchingIsStarred = true;

    await element.updateComplete;

    const star = element.shadowRoot.querySelector('button');
    assert.isTrue(star.disabled);
  });

  it('_starredIssues changes displayed icon', async () => {
    element.issueRef = {projectName: 'proj', localId: 1};

    element._starredIssues = new Set([issueRefToString(element.issueRef)]);

    await element.updateComplete;

    const star = element.shadowRoot.querySelector('button');
    assert.equal(star.textContent.trim(), 'star');

    element._starredIssues = new Set();

    await element.updateComplete;

    assert.equal(star.textContent.trim(), 'star_border');
  });
});
