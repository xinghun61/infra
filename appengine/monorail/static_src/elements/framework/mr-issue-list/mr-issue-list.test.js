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
  });

  afterEach(() => {
    document.body.removeChild(element);
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

  it('selected disabled when selectionEnabled is false', async () => {
    element.selectionEnabled = false;
    element.issues = [
      {summary: 'test issue'},
      {summary: 'I have a summary'},
    ];

    await element.updateComplete;

    const checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');

    assert.equal(checkboxes.length, 0);
  });

  it('selected issues render selected attribute', async () => {
    element.selectionEnabled = true;
    element.issues = [
      {summary: 'issue 1'},
      {summary: 'another issue'},
      {summary: 'issue 2'},
    ];
    element.columns = ['Summary'];

    await element.updateComplete;

    element._selectedIssues = [true, false, false];

    await element.updateComplete;

    const issues = element.shadowRoot.querySelectorAll('tr[selected]');

    assert.equal(issues.length, 1);
    assert.equal(issues[0].dataset.index, '0');
    assert.include(issues[0].textContent, 'issue 1');
  });

  it('selected issues added when issues checked', async () => {
    element.selectionEnabled = true;
    element.issues = [
      {summary: 'issue 1'},
      {summary: 'another issue'},
      {summary: 'issue 2'},
    ];

    await element.updateComplete;

    assert.deepEqual(element.selectedIssues, []);

    const checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');

    assert.equal(checkboxes.length, 3);

    checkboxes[2].checked = true;
    checkboxes[2].dispatchEvent(new CustomEvent('change'));

    await element.updateComplete;

    assert.deepEqual(element.selectedIssues, [
      {summary: 'issue 2'},
    ]);

    checkboxes[0].checked = true;
    checkboxes[0].dispatchEvent(new CustomEvent('change'));

    await element.updateComplete;

    assert.deepEqual(element.selectedIssues, [
      {summary: 'issue 1'},
      {summary: 'issue 2'},
    ]);
  });

  describe('hot keys', () => {
    beforeEach(() => {
      element.issues = [
        {localId: 1},
        {localId: 2},
        {localId: 3},
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
      element.issues = [{localId: 2}];
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

    it('pressing x selects focused issue', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');
      row.dispatchEvent(new KeyboardEvent('keydown', {key: 'x'}));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 2},
      ]);
    });

    it('pressing o navigates to focused issue', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');
      row.dispatchEvent(new KeyboardEvent('keydown', {key: 'o'}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(element._navigateToIssue, {localId: 2}, false);
    });

    it('pressing shift+o opens focused issue in new tab', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');
      row.dispatchEvent(new KeyboardEvent('keydown',
        {key: 'O', shiftKey: true}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(element._navigateToIssue, {localId: 2}, true);
    });
  });
});

