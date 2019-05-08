// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
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

  it('_loadIssuePage loads issue page', async () => {
    await element._loadIssuePage({
      query: {id: '234'},
      params: {project: 'chromium'},
    });

    const issuePage = element.shadowRoot.querySelector('mr-issue-page');
    assert.isDefined(issuePage, 'issue page is defined');
    assert.equal(issuePage.issueRef.projectName, 'chromium');
    assert.equal(issuePage.issueRef.localId, 234);
  });
});
