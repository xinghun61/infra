// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrApp} from './mr-app.js';


let element;

window.CS_env = {
  token: 'foo-token',
};

describe('mr-app', () => {
  beforeEach(() => {
    element = document.createElement('mr-app');
    document.body.appendChild(element);
    element.formsToCheck = [];
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrApp);
  });

  it('_universalRouteHandler calls next()', () => {
    const ctx = {};
    const next = sinon.stub();

    element._universalRouteHandler(ctx, next);

    sinon.assert.calledOnce(next);
  });

  it('_universalRouteHandler parses queryParams', () => {
    const ctx = {querystring: 'q=owner:me&colspec=Summary'};
    const next = sinon.stub();
    element._universalRouteHandler(ctx, next);

    assert.deepEqual(element.queryParams, {q: 'owner:me', colspec: 'Summary'});
  });

  it('_universalRouteHandler ignores case for queryParams keys', () => {
    const ctx = {querystring: 'Q=owner:me&ColSpeC=Summary&x=owner'};
    const next = sinon.stub();
    element._universalRouteHandler(ctx, next);

    assert.deepEqual(element.queryParams, {q: 'owner:me', colspec: 'Summary',
      x: 'owner'});
  });

  it('_loadIssuePage loads issue page', async () => {
    await element._loadIssuePage({
      query: {id: '234'},
      params: {project: 'chromium'},
    });
    await element.updateComplete;

    // Check that only one page element is rendering at a time.
    const main = element.shadowRoot.querySelector('main');
    assert.equal(main.children.length, 1);

    const issuePage = element.shadowRoot.querySelector('mr-issue-page');
    assert.isDefined(issuePage, 'issue page is defined');
    assert.equal(issuePage.issueRef.projectName, 'chromium');
    assert.equal(issuePage.issueRef.localId, 234);
  });

  it('_loadListPage loads list page', async () => {
    await element._loadListPage({
      params: {project: 'chromium'},
    });
    await element.updateComplete;

    // Check that only one page element is rendering at a time.
    const main = element.shadowRoot.querySelector('main');
    assert.equal(main.children.length, 1);

    const listPage = element.shadowRoot.querySelector('mr-list-page');
    assert.isDefined(listPage, 'list page is defined');
    assert.equal(listPage.projectName, 'chromium');
  });

  it('_loadListPage loads grid page', async () => {
    element.queryParams = {mode: 'grid'};
    await element._loadListPage({
      params: {project: 'chromium'},
    });
    await element.updateComplete;

    // Check that only one page element is rendering at a time.
    const main = element.shadowRoot.querySelector('main');
    assert.equal(main.children.length, 1);

    const gridPage = element.shadowRoot.querySelector('mr-grid-page');
    assert.isDefined(gridPage, 'grid page is defined');
    assert.equal(gridPage.projectName, 'chromium');
  });
});
