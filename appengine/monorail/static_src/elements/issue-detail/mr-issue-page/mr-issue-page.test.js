// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {assert} from 'chai';
import sinon from 'sinon';
import {MrIssuePage} from './mr-issue-page.js';
import {store} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import {prpcClient} from 'prpc-client-instance.js';

let element;
let loadingElement;
let fetchErrorElement;
let deletedElement;
let movedElement;
let issueElement;

function populateElementReferences() {
  flush();
  loadingElement = element.shadowRoot.querySelector('#loading');
  fetchErrorElement = element.shadowRoot.querySelector('#fetch-error');
  deletedElement = element.shadowRoot.querySelector('#deleted');
  movedElement = element.shadowRoot.querySelector('#moved');
  issueElement = element.shadowRoot.querySelector('#issue');
}

describe('mr-issue-page', () => {
  beforeEach(() => {
    element = document.createElement('mr-issue-page');
    document.body.appendChild(element);
    sinon.stub(prpcClient, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);
    prpcClient.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrIssuePage);
  });

  it('issue not loaded yet', () => {
    element.fetchingIssue = true;

    populateElementReferences();

    assert.isNotNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  it('no loading on future issue fetches', () => {
    element.issue = {localId: 222};
    element.fetchingIssue = true;

    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNotNull(issueElement);
  });

  it('fetch error', () => {
    element.fetchingIssue = false;
    element.fetchIssueError = 'error';
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNotNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  it('deleted issue', () => {
    element.fetchingIssue = false;
    element.issue = {isDeleted: true};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNotNull(deletedElement);
    assert.isNull(issueElement);
  });

  it('normal issue', () => {
    element.fetchingIssue = false;
    element.issue = {localId: 111};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNotNull(issueElement);
  });

  it('code font pref toggles attribute', () => {
    assert.isFalse(element.codeFont);
    assert.isFalse(element.hasAttribute('code-font'));

    element.prefs = new Map([['code_font', 'true']]);

    assert.isTrue(element.codeFont);
    assert.isTrue(element.hasAttribute('code-font'));

    element.prefs = new Map([['code_font', 'false']]);

    assert.isFalse(element.codeFont);
    assert.isFalse(element.hasAttribute('code-font'));
  });

  it('undeleting issue only shown if you have permissions', async () => {
    element.issue = {isDeleted: true};

    populateElementReferences();

    assert.isNotNull(deletedElement);

    let button = element.shadowRoot.querySelector('.undelete');
    assert.isNull(button);

    element.issuePermissions = ['deleteissue'];
    flush();

    button = element.shadowRoot.querySelector('.undelete');
    assert.isNotNull(button);
  });

  it('undeleting issue updates page with issue', async () => {
    const issueRef = {localId: 111, projectName: 'test'};
    const deletedIssuePromise = Promise.resolve({
      issue: {isDeleted: true},
    });
    const issuePromise = Promise.resolve({
      issue: {localId: 111, projectName: 'test'},
    });
    const deletePromise = Promise.resolve({});
    sinon.spy(element, '_undeleteIssue');
    prpcClient.call.withArgs('monorail.Issues', 'GetIssue', {issueRef})
      .onFirstCall().returns(deletedIssuePromise)
      .onSecondCall().returns(issuePromise);
    prpcClient.call.withArgs('monorail.Issues', 'DeleteIssue',
      {delete: false, issueRef}).returns(deletePromise);

    store.dispatch(
      issue.setIssueRef(issueRef.localId, issueRef.projectName));

    await deletedIssuePromise;

    populateElementReferences();

    assert.deepEqual(element.issue, {isDeleted: true});
    assert.isNull(issueElement);
    assert.isNotNull(deletedElement);

    // Make undelete button visible. This must be after deletedIssuePromise
    // resolves since issuePermissions are cleared by Redux after that promise.
    element.issuePermissions = ['deleteissue'];
    flush();

    const button = element.shadowRoot.querySelector('.undelete');
    button.click();

    sinon.assert.calledWith(prpcClient.call, 'monorail.Issues', 'GetIssue',
      {issueRef});
    sinon.assert.calledWith(prpcClient.call, 'monorail.Issues', 'DeleteIssue',
      {delete: false, issueRef});

    await deletePromise;
    await issuePromise;

    assert.isTrue(element._undeleteIssue.calledOnce);

    assert.deepEqual(element.issue, {localId: 111, projectName: 'test'});

    populateElementReferences();
    assert.isNotNull(issueElement);

    element._undeleteIssue.restore();
  });

  it('issue has moved', () => {
    element.fetchingIssue = false;
    element.issue = {movedToRef: {projectName: 'hello', localId: 10}};

    populateElementReferences();

    assert.isNull(issueElement);
    assert.isNull(deletedElement);
    assert.isNotNull(movedElement);

    const link = movedElement.querySelector('.new-location');
    assert.equal(link.getAttribute('href'), '/p/hello/issues/detail?id=10');
  });

  it('moving to a restricted issue', () => {
    element.fetchingIssue = false;
    element.issue = {localId: 111};

    flush();

    element.issue = {localId: 222};
    element.fetchIssueError = 'error';

    populateElementReferences();
    flush();

    assert.isNull(loadingElement);
    assert.isNotNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(movedElement);
    // TODO(ehmaldonado): Replace with isNull once mr-issue-page is converted to
    // lit-element.
    assert.equal(window.getComputedStyle(issueElement).display, 'none');
  });
});
