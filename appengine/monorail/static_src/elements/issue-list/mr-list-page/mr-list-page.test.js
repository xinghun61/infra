// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import sinon from 'sinon';
import {assert} from 'chai';
import {prpcClient} from 'prpc-client-instance.js';
import {MrListPage, DEFAULT_ISSUES_PER_PAGE} from './mr-list-page.js';

let element;

describe('mr-list-page', () => {
  beforeEach(() => {
    element = document.createElement('mr-list-page');
    document.body.appendChild(element);
    sinon.stub(prpcClient, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);
    prpcClient.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrListPage);
  });

  it('shows loading when issues loading', async () => {
    element.fetchingIssueList = true;

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');
    const snackbar = element.shadowRoot.querySelector('chops-snackbar');

    assert.equal(loading.textContent.trim(), 'Loading...');
    assert.isNull(noIssues);
    assert.isNull(issueList);
    assert.isNull(snackbar);
  });

  it('does not clear existing issue list when loading new issues', async () => {
    element.fetchingIssueList = true;
    element.totalIssues = 1;
    element.issues = [{localId: 1, projectName: 'chromium'}];

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');
    const snackbar = element.shadowRoot.querySelector('chops-snackbar');

    assert.isNull(loading);
    assert.isNull(noIssues);
    assert.isNotNull(issueList);
    assert.isNotNull(snackbar);
  });

  it('shows list when done loading', async () => {
    element.fetchingIssueList = false;
    element.totalIssues = 100;

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');
    const snackbar = element.shadowRoot.querySelector('chops-snackbar');

    assert.isNull(loading);
    assert.isNull(noIssues);
    assert.isNotNull(issueList);
    assert.isNull(snackbar);
  });

  it('shows no issues when no search results', async () => {
    element.fetchingIssueList = false;
    element.totalIssues = 0;
    element.queryParams = {q: 'owner:me'};

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.isNull(loading);
    assert.isNotNull(noIssues);
    assert.isNull(issueList);

    assert.equal(noIssues.querySelector('strong').textContent.trim(),
        'owner:me');
  });

  it('offers consider closed issues when no open results', async () => {
    element.fetchingIssueList = false;
    element.totalIssues = 0;
    element.queryParams = {q: 'owner:me', can: '2'};

    await element.updateComplete;

    const considerClosed = element.shadowRoot.querySelector('.consider-closed');

    assert.isFalse(considerClosed.hidden);

    element.queryParams = {q: 'owner:me', can: '1'};
    element.fetchingIssueList = false;

    await element.updateComplete;

    assert.isTrue(considerClosed.hidden);
  });

  it('refreshes when queryParams.q changes', async () => {
    element.queryParams = {};
    await element.updateComplete;

    sinon.stub(element, 'refresh');

    element.queryParams = {colspec: 'Summary+ID'};

    await element.updateComplete;
    sinon.assert.notCalled(element.refresh);

    element.queryParams = {q: 'owner:me'};

    await element.updateComplete;
    sinon.assert.calledOnce(element.refresh);
  });

  it('startIndex parses queryParams for value', () => {
    // Default value.
    element.queryParams = {};
    assert.equal(element.startIndex, 0);

    // Int.
    element.queryParams = {start: 2};
    assert.equal(element.startIndex, 2);

    // String.
    element.queryParams = {start: '5'};
    assert.equal(element.startIndex, 5);

    // Negative value.
    element.queryParams = {start: -5};
    assert.equal(element.startIndex, 0);

    // NaN
    element.queryParams = {start: 'lol'};
    assert.equal(element.startIndex, 0);
  });

  it('maxItems parses queryParams for value', () => {
    // Default value.
    element.queryParams = {};
    assert.equal(element.maxItems, DEFAULT_ISSUES_PER_PAGE);

    // Int.
    element.queryParams = {num: 50};
    assert.equal(element.maxItems, 50);

    // String.
    element.queryParams = {num: '33'};
    assert.equal(element.maxItems, 33);

    // NaN
    element.queryParams = {num: 'lol'};
    assert.equal(element.maxItems, DEFAULT_ISSUES_PER_PAGE);
  });

  it('parses groupby parameter correctly', () => {
    element.queryParams = {groupby: 'Priority+Status'};

    assert.deepEqual(element.groups,
        ['Priority', 'Status']);
  });

  it('groupby parsing preserves dashed parameters', () => {
    element.queryParams = {groupby: 'Priority+Custom-Status'};

    assert.deepEqual(element.groups,
        ['Priority', 'Custom-Status']);
  });

  describe('pagination', () => {
    beforeEach(() => {
      // Stop Redux from overriding values being tested.
      sinon.stub(element, 'stateChanged');
    });

    it('issue count hidden when no issues', async () => {
      element.queryParams = {num: 10, start: 0};
      element.totalIssues = 0;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.isTrue(count.hidden);
    });

    it('issue count renders on first page', async () => {
      element.queryParams = {num: 10, start: 0};
      element.totalIssues = 100;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '1 - 10 of 100');
    });

    it('issue count renders on middle page', async () => {
      element.queryParams = {num: 10, start: 50};
      element.totalIssues = 100;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '51 - 60 of 100');
    });

    it('issue count renders on last page', async () => {
      element.queryParams = {num: 10, start: 95};
      element.totalIssues = 100;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '96 - 100 of 100');
    });

    it('issue count renders on single page', async () => {
      element.queryParams = {num: 100, start: 0};
      element.totalIssues = 33;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '1 - 33 of 33');
    });

    it('next and prev hidden on single page', async () => {
      element.queryParams = {num: 500, start: 0};
      element.totalIssues = 10;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNull(next);
      assert.isNull(prev);
    });

    it('prev hidden on first page', async () => {
      element.queryParams = {num: 10, start: 0};
      element.totalIssues = 30;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNotNull(next);
      assert.isNull(prev);
    });

    it('next hidden on last page', async () => {
      element.queryParams = {num: 10, start: 9};
      element.totalIssues = 5;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNull(next);
      assert.isNotNull(prev);
    });

    it('next and prev shown on middle page', async () => {
      element.queryParams = {num: 10, start: 50};
      element.totalIssues = 100;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNotNull(next);
      assert.isNotNull(prev);
    });
  });

  describe('edit actions', () => {
    beforeEach(() => {
      sinon.stub(window, 'alert');

      // Give the test user edit privileges.
      element._isLoggedIn = true;
      element._currentUser = {isSiteAdmin: true};
    });

    afterEach(() => {
      window.alert.restore();
    });

    it('edit actions hidden when user is logged out', async () => {
      element._isLoggedIn = false;

      await element.updateComplete;

      const editActions = element.shadowRoot.querySelector('.edit-actions');
      assert.isFalse(editActions.children.length > 0);
    });

    it('edit actions hidden when user is not a project member', async () => {
      element._isLoggedIn = true;
      element._currentUser = {displayName: 'regular@user.com'};

      await element.updateComplete;

      const editActions = element.shadowRoot.querySelector('.edit-actions');
      assert.isFalse(editActions.children.length > 0);
    });

    it('edit actions shown when user is a project member', async () => {
      element.projectName = 'chromium';
      element._isLoggedIn = true;
      element._currentUser = {isSiteAdmin: false, userId: '123'};
      element._usersProjects = new Map([['123', {ownerOf: ['chromium']}]]);

      await element.updateComplete;

      const editActions = element.shadowRoot.querySelector('.edit-actions');
      assert.isTrue(editActions.children.length > 0);

      element.projectName = 'nonmember-project';
      await element.updateComplete;

      assert.isFalse(editActions.children.length > 0);
    });

    it('edit actions shown when user is a site admin', async () => {
      element._isLoggedIn = true;
      element._currentUser = {isSiteAdmin: true};

      await element.updateComplete;

      const editActions = element.shadowRoot.querySelector('.edit-actions');
      assert.isTrue(editActions.children.length > 0);
    });

    it('bulk edit stops when no issues selected', () => {
      element.selectedIssues = [];
      element.projectName = 'test';

      element.bulkEdit();

      sinon.assert.calledWith(window.alert,
          'Please select some issues to edit.');
    });

    it('bulk edit redirects to bulk edit page', () => {
      element.page = sinon.stub();
      element.selectedIssues = [
        {localId: 1},
        {localId: 2},
      ];
      element.projectName = 'test';

      element.bulkEdit();

      sinon.assert.calledWith(element.page,
          '/p/test/issues/bulkedit?ids=1%2C2');
    });

    it('flag issue as spam stops when no issues selected', () => {
      element.selectedIssues = [];

      element._flagIssues(true);

      sinon.assert.calledWith(window.alert,
          'Please select some issues to flag as spam.');
    });

    it('un-flag issue as spam stops when no issues selected', () => {
      element.selectedIssues = [];

      element._flagIssues(false);

      sinon.assert.calledWith(window.alert,
          'Please select some issues to un-flag as spam.');
    });

    it('flagging issues as spam sends pRPC request', async () => {
      element.page = sinon.stub();
      element.selectedIssues = [
        {localId: 1, projectName: 'test'},
        {localId: 2, projectName: 'test'},
      ];

      await element._flagIssues(true);

      sinon.assert.calledWith(prpcClient.call, 'monorail.Issues',
          'FlagIssues', {
            issueRefs: [
              {localId: 1, projectName: 'test'},
              {localId: 2, projectName: 'test'},
            ],
            flag: true,
          });
    });

    it('un-flagging issues as spam sends pRPC request', async () => {
      element.page = sinon.stub();
      element.selectedIssues = [
        {localId: 1, projectName: 'test'},
        {localId: 2, projectName: 'test'},
      ];

      await element._flagIssues(false);

      sinon.assert.calledWith(prpcClient.call, 'monorail.Issues',
          'FlagIssues', {
            issueRefs: [
              {localId: 1, projectName: 'test'},
              {localId: 2, projectName: 'test'},
            ],
            flag: false,
          });
    });

    it('clicking change columns opens dialog', async () => {
      await element.updateComplete;
      const button = element.shadowRoot.querySelector('.change-columns-button');
      const dialog = element.shadowRoot.querySelector('mr-change-columns');
      sinon.stub(dialog, 'open');

      button.click();

      sinon.assert.calledOnce(dialog.open);
    });

    it('add to hotlist stops when no issues selected', () => {
      element.selectedIssues = [];
      element.projectName = 'test';

      element.addToHotlist();

      sinon.assert.calledWith(window.alert,
          'Please select some issues to add to hotlists.');
    });

    it('add to hotlist dialog opens', async () => {
      element.selectedIssues = [
        {localId: 1, projectName: 'test'},
        {localId: 2, projectName: 'test'},
      ];
      element.projectName = 'test';

      await element.updateComplete;

      const dialog = element.shadowRoot.querySelector(
          'mr-update-issue-hotlists');

      sinon.stub(dialog, 'open');

      element.addToHotlist();

      sinon.assert.calledOnce(dialog.open);
    });
  });
});

