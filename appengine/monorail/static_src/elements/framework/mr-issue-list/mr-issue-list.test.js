// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import sinon from 'sinon';
import {MrIssueList} from './mr-issue-list.js';

let element;

const listRowIsFocused = (element, i) => {
  const focused = element.shadowRoot.activeElement;
  assert.equal(focused.tagName.toUpperCase(), 'TR');
  assert.equal(focused.dataset.index, `${i}`);
};

describe('mr-issue-list', () => {
  beforeEach(() => {
    element = document.createElement('mr-issue-list');
    document.body.appendChild(element);

    sinon.stub(element, '_baseUrl').returns('/p/chromium/issues/list');
    sinon.stub(element, '_page');
    sinon.stub(window, 'open');
  });

  afterEach(() => {
    document.body.removeChild(element);
    window.open.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrIssueList);
  });

  it('issue summaries render', async () => {
    element.issues = [
      {summary: 'test issue'},
      {summary: 'I have a summary'},
    ];
    element.columns = ['Summary'];

    await element.updateComplete;

    const summaries = element.shadowRoot.querySelectorAll('.col-summary');

    assert.equal(summaries.length, 2);

    assert.equal(summaries[0].textContent.trim(), 'test issue');
    assert.equal(summaries[1].textContent.trim(), 'I have a summary');
  });

  it('one word labels render in summary column', async () => {
    element.issues = [
      {
        summary: 'test issue',
        labelRefs: [
          {label: 'ignore-multi-word-labels'},
          {label: 'Security'},
          {label: 'A11y'},
        ],
      },
    ];
    element.columns = ['Summary'];

    await element.updateComplete;

    const summary = element.shadowRoot.querySelector('.col-summary');
    const labels = summary.querySelectorAll('.summary-label');

    assert.equal(labels.length, 2);

    assert.equal(labels[0].textContent.trim(), 'Security');
    assert.include(labels[0].href,
        '/p/chromium/issues/list?q=label%3ASecurity');
    assert.equal(labels[1].textContent.trim(), 'A11y');
    assert.include(labels[1].href,
        '/p/chromium/issues/list?q=label%3AA11y');
  });

  it('clicking issue link does not trigger _navigateToIssue', async () => {
    sinon.stub(element, '_navigateToIssue');

    // Prevent the page from actually navigating on the link click.
    const clickIntercepter = sinon.spy((e) => {
      e.preventDefault();
    });
    window.addEventListener('click', clickIntercepter);

    element.issues = [
      {summary: 'test issue'},
      {summary: 'I have a summary'},
    ];
    element.columns = ['ID'];

    await element.updateComplete;

    const idLink = element.shadowRoot.querySelector('.col-id > mr-issue-link');

    idLink.click();

    sinon.assert.calledOnce(clickIntercepter);
    sinon.assert.notCalled(element._navigateToIssue);

    window.removeEventListener('click', clickIntercepter);
  });

  it('clicking issue row opens issue', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 22,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.click();

    sinon.assert.calledWith(element._page, '/p/chromium/issues/detail?id=22');
    sinon.assert.notCalled(window.open);
  });

  it('ctrl+click on row on opens issue in new tab', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 24,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.dispatchEvent(new MouseEvent('click',
        {ctrlKey: true, bubbles: true}));

    sinon.assert.calledWith(window.open,
        '/p/chromium/issues/detail?id=24', '_blank', 'noopener');
  });

  it('meta+click on row on opens issue in new tab', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 24,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.dispatchEvent(new MouseEvent('click',
        {metaKey: true, bubbles: true}));

    sinon.assert.calledWith(window.open,
        '/p/chromium/issues/detail?id=24', '_blank', 'noopener');
  });

  it('mouse wheel click on row on opens issue in new tab', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 24,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.dispatchEvent(new MouseEvent('auxclick',
        {button: 1, bubbles: true}));

    sinon.assert.calledWith(window.open,
        '/p/chromium/issues/detail?id=24', '_blank', 'noopener');
  });

  it('AllLabels column renders', async () => {
    element.issues = [
      {labelRefs: [{label: 'test'}, {label: 'hello-world'}]},
      {labelRefs: [{label: 'one-label'}]},
    ];

    element.columns = ['AllLabels'];

    await element.updateComplete;

    const labels = element.shadowRoot.querySelectorAll('.col-alllabels');

    assert.equal(labels.length, 2);

    assert.equal(labels[0].textContent.trim(), 'test, hello-world');
    assert.equal(labels[1].textContent.trim(), 'one-label');
  });

  it('issues sorted into groups when groups defined', async () => {
    element.issues = [
      {ownerRef: {displayName: 'test@example.com'}},
      {ownerRef: {displayName: 'test@example.com'}},
      {ownerRef: {displayName: 'other.user@example.com'}},
      {},
    ];

    element.columns = ['Owner'];
    element.groups = ['Owner'];

    await element.updateComplete;

    const owners = element.shadowRoot.querySelectorAll('.col-owner');
    assert.equal(owners.length, 4);

    const groupHeaders = element.shadowRoot.querySelectorAll(
        '.group-header');
    assert.equal(groupHeaders.length, 3);

    assert.include(groupHeaders[0].textContent,
        '2 issues: Owner=test@example.com');
    assert.include(groupHeaders[1].textContent,
        '1 issue: Owner=other.user@example.com');
    assert.include(groupHeaders[2].textContent, '1 issue: -has:Owner');
  });

  it('toggling group hides members', async () => {
    element.issues = [
      {ownerRef: {displayName: 'group1@example.com'}},
      {ownerRef: {displayName: 'group2@example.com'}},
    ];

    element.columns = ['Owner'];
    element.groups = ['Owner'];

    await element.updateComplete;

    const issueRows = element.shadowRoot.querySelectorAll('.list-row');
    assert.equal(issueRows.length, 2);

    assert.isFalse(issueRows[0].hidden);
    assert.isFalse(issueRows[1].hidden);

    const groupHeaders = element.shadowRoot.querySelectorAll(
        '.group-header');
    assert.equal(groupHeaders.length, 2);

    // Toggle first group hidden.
    groupHeaders[0].click();
    await element.updateComplete;

    assert.isTrue(issueRows[0].hidden);
    assert.isFalse(issueRows[1].hidden);
  });

  it('reloadColspec navigates to page with new colspec', () => {
    element.columns = ['ID', 'Summary'];
    element.queryParams = {};

    element.reloadColspec(['Summary', 'AllLabels']);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?colspec=Summary%2BAllLabels');
  });

  it('updateSortSpec navigates to page with new sort option', async () => {
    element.columns = ['ID', 'Summary'];
    element.queryParams = {};

    await element.updateComplete;

    element.updateSortSpec('Summary', true);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?sort=-summary');
  });

  it('updateSortSpec navigates to first page when on later page', async () => {
    element.columns = ['ID', 'Summary'];
    element.queryParams = {start: '100', q: 'owner:me'};

    await element.updateComplete;

    element.updateSortSpec('Summary', true);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?q=owner%3Ame&sort=-summary');
  });

  it('updateSortSpec prepends new option to existing sort', async () => {
    element.columns = ['ID', 'Summary', 'Owner'];
    element.queryParams = {sort: '-summary+owner'};

    await element.updateComplete;

    element.updateSortSpec('ID');

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?sort=id%20-summary%20owner');
  });

  it('updateSortSpec removes existing instances of sorted column', async () => {
    element.columns = ['ID', 'Summary', 'Owner'];
    element.queryParams = {sort: '-summary+owner+owner'};

    await element.updateComplete;

    element.updateSortSpec('Owner', true);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?sort=-owner%20-summary');
  });

  it('_uniqueValuesByColumn re-computed when values update', async () => {
    element.issues = [
      {id: 1, projectName: 'chromium'},
      {id: 2, projectName: 'chromium'},
      {id: 3, projectName: 'chrOmiUm'},
      {id: 1, projectName: 'other'},
    ];
    element.columns = [];
    await element.updateComplete;

    assert.deepEqual(element._uniqueValuesByColumn, new Map());

    element.columns = ['project'];
    await element.updateComplete;

    assert.deepEqual(element._uniqueValuesByColumn,
        new Map([['project', new Set(['chromium', 'other'])]]));
  });

  it('showOnly adds new search term to query', async () => {
    element.currentQuery = 'owner:me';
    element.queryParams = {};

    await element.updateComplete;

    element.showOnly('Priority', 'High');

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?q=owner%3Ame%20priority%3DHigh');
  });

  it('addGroupBy updates groupby URL param', async () => {
    element.columns = ['Owner', 'Priority'];
    element.groups = ['Status'];

    element.addGroupBy(0);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?groupby=Owner%20Status&colspec=Priority');
  });

  it('addColumn adds a column', () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'reloadColspec');

    element.addColumn('AllLabels');

    sinon.assert.calledWith(element.reloadColspec,
        ['ID', 'Summary', 'AllLabels']);
  });

  it('removeColumn removes a column', () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'reloadColspec');

    element.removeColumn(0);

    sinon.assert.calledWith(element.reloadColspec, ['Summary']);
  });

  it('clicking sort up column header sets sort spec', async () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'updateSortSpec');

    await element.updateComplete;

    const dropdown = element.shadowRoot.querySelector('.dropdown-summary');

    dropdown.clickItem(0); // Sort up.

    sinon.assert.calledWith(element.updateSortSpec, 'Summary');
  });

  it('clicking sort down column header sets sort spec', async () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'updateSortSpec');

    await element.updateComplete;

    const dropdown = element.shadowRoot.querySelector('.dropdown-summary');

    dropdown.clickItem(1); // Sort down.

    sinon.assert.calledWith(element.updateSortSpec, 'Summary', true);
  });

  it('clicking hide column in column header removes column', async () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'removeColumn');

    await element.updateComplete;

    const dropdown = element.shadowRoot.querySelector('.dropdown-summary');

    dropdown.clickItem(2); // Hide column.

    sinon.assert.calledWith(element.removeColumn, 1);
  });

  it('starring disabled when starringEnabled is false', async () => {
    element.starringEnabled = false;
    element.issues = [
      {summary: 'test issue'},
      {summary: 'I have a summary'},
    ];

    await element.updateComplete;

    let stars = element.shadowRoot.querySelectorAll('mr-star-button');
    assert.equal(stars.length, 0);

    element.starringEnabled = true;
    await element.updateComplete;

    stars = element.shadowRoot.querySelectorAll('mr-star-button');
    assert.equal(stars.length, 2);
  });

  describe('issue selection', () => {
    beforeEach(() => {
      element.selectionEnabled = true;
    });

    it('selections disabled when selectionEnabled is false', async () => {
      element.selectionEnabled = false;
      element.issues = [
        {summary: 'test issue'},
        {summary: 'I have a summary'},
      ];

      await element.updateComplete;

      let checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');
      assert.equal(checkboxes.length, 0);

      element.selectionEnabled = true;
      await element.updateComplete;

      checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');
      assert.equal(checkboxes.length, 2);
    });

    it('selected issues render selected attribute', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'another issue', localId: 2, projectName: 'proj'},
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ];
      element.columns = ['Summary'];

      await element.updateComplete;

      element._selectedIssues = new Set(['proj:1']);

      await element.updateComplete;

      const issues = element.shadowRoot.querySelectorAll('tr[selected]');

      assert.equal(issues.length, 1);
      assert.equal(issues[0].dataset.index, '0');
      assert.include(issues[0].textContent, 'issue 1');
    });

    it('clicking select all selects all issues', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ];

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, []);

      const selectAll = element.shadowRoot.querySelector('.select-all');
      selectAll.click();

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ]);
    });

    it('when checked select all deselects all issues', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ];

      await element.updateComplete;

      element._selectedIssues = new Set(['proj:1', 'proj:2']);

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ]);

      const selectAll = element.shadowRoot.querySelector('.select-all');
      selectAll.click();

      assert.deepEqual(element.selectedIssues, []);
    });

    it('selected issues added when issues checked', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'another issue', localId: 2, projectName: 'proj'},
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ];

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, []);

      const checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');

      assert.equal(checkboxes.length, 3);

      checkboxes[2].dispatchEvent(new MouseEvent('click'));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ]);

      checkboxes[0].dispatchEvent(new MouseEvent('click'));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ]);
    });

    it('shift+click selects issues in a range', async () => {
      element.issues = [
        {localId: 1, projectName: 'proj'},
        {localId: 2, projectName: 'proj'},
        {localId: 3, projectName: 'proj'},
        {localId: 4, projectName: 'proj'},
        {localId: 5, projectName: 'proj'},
      ];

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, []);

      const checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');

      // First click.
      checkboxes[0].dispatchEvent(new MouseEvent('click'));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 1, projectName: 'proj'},
      ]);

      // Second click.
      checkboxes[3].dispatchEvent(new MouseEvent('click', {shiftKey: true}));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 1, projectName: 'proj'},
        {localId: 2, projectName: 'proj'},
        {localId: 3, projectName: 'proj'},
        {localId: 4, projectName: 'proj'},
      ]);

      // It's possible to chain Shift+Click operations.
      checkboxes[2].dispatchEvent(new MouseEvent('click', {shiftKey: true}));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 1, projectName: 'proj'},
        {localId: 2, projectName: 'proj'},
      ]);
    });
  });

  describe('hot keys', () => {
    beforeEach(() => {
      element.issues = [
        {localId: 1, projectName: 'chromium'},
        {localId: 2, projectName: 'chromium'},
        {localId: 3, projectName: 'chromium'},
      ];

      element.selectionEnabled = true;

      sinon.stub(element, '_navigateToIssue');
    });

    afterEach(() => {
      element._navigateToIssue.restore();
    });

    it('global keydown listener removed on disconnect', async () => {
      sinon.stub(element, '_boundRunNavigationHotKeys');

      await element.updateComplete;

      window.dispatchEvent(new Event('keydown'));
      sinon.assert.calledOnce(element._boundRunNavigationHotKeys);

      document.body.removeChild(element);

      window.dispatchEvent(new Event('keydown'));
      sinon.assert.calledOnce(element._boundRunNavigationHotKeys);

      document.body.appendChild(element);
    });

    it('pressing j defaults to first issue', async () => {
      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 0);
    });

    it('pressing j focuses next issue', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-0').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 1);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 2);
    });

    it('pressing j at the end of the list loops around', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-2').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 0);
    });


    it('pressing k defaults to last issue', async () => {
      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 2);
    });

    it('pressing k focuses previous issue', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-2').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 1);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 0);
    });

    it('pressing k at the start of the list loops around', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-0').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 2);
    });

    it('j and k keys treat row as focused if child is focused', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-1').querySelector(
          'mr-issue-link').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      listRowIsFocused(element, 2);

      element.shadowRoot.querySelector('.row-1').querySelector(
          'mr-issue-link').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      listRowIsFocused(element, 0);
    });

    it('j and k keys stay on one element when one issue', async () => {
      element.issues = [{localId: 2, projectName: 'chromium'}];
      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      listRowIsFocused(element, 0);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      listRowIsFocused(element, 0);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      listRowIsFocused(element, 0);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      listRowIsFocused(element, 0);
    });

    it('j and k no-op when event is from input', async () => {
      const input = document.createElement('input');
      document.body.appendChild(input);

      await element.updateComplete;

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      assert.isNull(element.shadowRoot.activeElement);

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      assert.isNull(element.shadowRoot.activeElement);

      document.body.removeChild(input);
    });

    it('j and k no-op when event is from shadowDOM input', async () => {
      const input = document.createElement('input');
      const root = document.createElement('div');

      root.attachShadow({mode: 'open'});
      root.shadowRoot.appendChild(input);

      document.body.appendChild(root);

      await element.updateComplete;

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      assert.isNull(element.shadowRoot.activeElement);

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      assert.isNull(element.shadowRoot.activeElement);

      document.body.removeChild(root);
    });

    it('pressing s stars focused issue', async () => {
      element.starringEnabled = true;
      sinon.stub(element, 'starIssue');
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');
      row.dispatchEvent(new KeyboardEvent('keydown', {key: 's'}));

      sinon.assert.calledWith(element.starIssue,
          {localId: 2, projectName: 'chromium'});
    });

    it('starIssue does not star issue while stars are fetched', () => {
      element.starringEnabled = true;
      sinon.stub(element, '_starIssue');
      element._fetchingStarredIssues = true;

      element.starIssue({localId: 2, projectName: 'chromium'});

      sinon.assert.notCalled(element._starIssue);
    });

    it('starIssue does not star when issue is being starred', () => {
      element.starringEnabled = true;
      sinon.stub(element, '_starIssue');
      element._starringIssues = new Map([['chromium:2', {requesting: true}]]);

      element.starIssue({localId: 2, projectName: 'chromium'});

      sinon.assert.notCalled(element._starIssue);
    });

    it('starIssue stars issue when issue is not being starred', () => {
      element.starringEnabled = true;
      sinon.stub(element, '_starIssue');
      element._starringIssues = new Map([['chromium:2', {requesting: false}]]);

      element.starIssue({localId: 2, projectName: 'chromium'});

      sinon.assert.calledWith(element._starIssue,
          {localId: 2, projectName: 'chromium'}, true);
    });

    it('starIssue unstars issue when issue is already starred', () => {
      element.starringEnabled = true;
      sinon.stub(element, '_starIssue');
      element._starredIssues = new Set(['chromium:2']);

      element.starIssue({localId: 2, projectName: 'chromium'});

      sinon.assert.calledWith(element._starIssue,
          {localId: 2, projectName: 'chromium'}, false);
    });

    it('pressing x selects focused issue', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');
      row.dispatchEvent(new KeyboardEvent('keydown', {key: 'x'}));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 2, projectName: 'chromium'},
      ]);
    });

    it('pressing o navigates to focused issue', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');
      row.dispatchEvent(new KeyboardEvent('keydown', {key: 'o'}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(element._navigateToIssue,
          {localId: 2, projectName: 'chromium'}, false);
    });

    it('pressing shift+o opens focused issue in new tab', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');
      row.dispatchEvent(new KeyboardEvent('keydown',
          {key: 'O', shiftKey: true}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(element._navigateToIssue,
          {localId: 2, projectName: 'chromium'}, true);
    });
  });
});

