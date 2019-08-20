// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import sinon from 'sinon';
import {assert} from 'chai';
import {prpcClient} from 'prpc-client-instance.js';
import {MrListPage} from './mr-list-page.js';

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

  it('shows loading only when issues loading', async () => {
    element.fetchingIssueList = true;

    await element.updateComplete;

    let loading = element.shadowRoot.querySelector('.container-no-issues');
    let issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.equal(loading.textContent.trim(), 'Loading...');
    assert.isNull(issueList);

    element.fetchingIssueList = false;

    await element.updateComplete;

    loading = element.shadowRoot.querySelector('.container-no-issues');
    issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.isNull(loading);
    assert.isNotNull(issueList);
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

  it('parses colspec parameter correctly', async () => {
    element.queryParams = {colspec: 'ID+Summary+AllLabels+Priority'};

    await element.updateComplete;

    assert.deepEqual(element.columns,
        ['ID', 'Summary', 'AllLabels', 'Priority']);
  });

  it('colspec parsing preserves dashed parameters', async () => {
    element.queryParams = {colspec: 'ID+Summary+Test-Label+Another-Label'};

    await element.updateComplete;

    assert.deepEqual(element.columns,
        ['ID', 'Summary', 'Test-Label', 'Another-Label']);
  });

  describe('edit actions', () => {
    beforeEach(() => {
      sinon.stub(window, 'alert');
    });

    afterEach(() => {
      window.alert.restore();
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

