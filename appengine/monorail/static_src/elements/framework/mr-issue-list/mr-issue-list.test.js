// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import {MrIssueList} from './mr-issue-list.js';

let element;

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
});

