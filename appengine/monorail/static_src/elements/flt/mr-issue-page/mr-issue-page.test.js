// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {assert} from 'chai';
import sinon from 'sinon';
import {MrIssuePage} from './mr-issue-page.js';
import * as issue from '../../redux/issue.js';

let element;
let loadingElement;
let fetchErrorElement;
let deletedElement;
let movedElement;
let issueElement;

let prpcStub;

function populateElementReferences() {
  flush();
  loadingElement = element.shadowRoot.querySelector('#loading');
  fetchErrorElement = element.shadowRoot.querySelector('#fetch-error');
  deletedElement = element.shadowRoot.querySelector('#deleted');
  movedElement = element.shadowRoot.querySelector('#moved');
  issueElement = element.shadowRoot.querySelector('#issue');
}

suite('mr-issue-page', () => {
  setup(() => {
    element = document.createElement('mr-issue-page');
    element.mapStateToProps = () => {};
    document.body.appendChild(element);

    prpcStub = sinon.stub(window.prpcClient, 'call');
  });

  teardown(() => {
    document.body.removeChild(element);

    prpcStub.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, MrIssuePage);
  });

  test('issue not loaded yet', () => {
    element.fetchingIssue = true;

    populateElementReferences();

    assert.isNotNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('no loading on future issue fetches', () => {
    element.issue = {localId: 222};
    element.fetchingIssue = true;

    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNotNull(issueElement);
  });

  test('fetch error', () => {
    element.fetchingIssue = false;
    element.fetchIssueError = 'error';
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNotNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('deleted issue', () => {
    element.fetchingIssue = false;
    element.issue = {isDeleted: true};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNotNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('normal issue', () => {
    element.fetchingIssue = false;
    element.issue = {localId: 111};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNotNull(issueElement);
  });

  test('code font pref toggles attribute', () => {
    assert.isFalse(element.codeFont);
    assert.isFalse(element.hasAttribute('code-font'));

    element.prefs = new Map([['code_font', 'true']]);

    assert.isTrue(element.codeFont);
    assert.isTrue(element.hasAttribute('code-font'));

    element.prefs = new Map([['code_font', 'false']]);

    assert.isFalse(element.codeFont);
    assert.isFalse(element.hasAttribute('code-font'));
  });

  test('undeleting issue only shown if you have permissions', async () => {
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

  test('undeleting issue updates page with issue', async () => {
    const issueRef = {localId: 111, projectName: 'test'};
    const deletedIssuePromise = Promise.resolve({
      issue: {isDeleted: true},
    });
    const issuePromise = Promise.resolve({
      issue: {localId: 111, projectName: 'test'},
    });
    const deletePromise = Promise.resolve({});
    sinon.spy(element, '_undeleteIssue');

    prpcStub.withArgs('monorail.Issues', 'GetIssue', {issueRef})
      .onFirstCall().returns(deletedIssuePromise)
      .onSecondCall().returns(issuePromise);
    prpcStub.withArgs('monorail.Issues', 'DeleteIssue',
      {delete: false, issueRef}).returns(deletePromise);

    element.dispatchAction(
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

    sinon.assert.calledWith(prpcStub, 'monorail.Issues', 'GetIssue',
      {issueRef});
    sinon.assert.calledWith(prpcStub, 'monorail.Issues', 'DeleteIssue',
      {delete: false, issueRef});

    await deletePromise;
    await issuePromise;

    assert.isTrue(element._undeleteIssue.calledOnce);

    assert.deepEqual(element.issue, {localId: 111, projectName: 'test'});

    populateElementReferences();
    assert.isNotNull(issueElement);

    element._undeleteIssue.restore();
  });

  test('issue has moved', () => {
    element.fetchingIssue = false;
    element.issue = {movedToRef: {projectName: 'hello', localId: 10}};

    populateElementReferences();

    assert.isNull(issueElement);
    assert.isNull(deletedElement);
    assert.isNotNull(movedElement);

    const link = movedElement.querySelector('.new-location');
    assert.equal(link.getAttribute('href'), '/p/hello/issues/detail?id=10');
  });
});
