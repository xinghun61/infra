// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import {MrGrid} from './mr-grid.js';
import {MrIssueLink} from
  'elements/framework/links/mr-issue-link/mr-issue-link.js';

let element;

describe('mr-grid', () => {
  beforeEach(() => {
    element = document.createElement('mr-grid');
    element.queryParams = {x: '', y: ''};
    element.issues = [{localId: 1, projectName: 'monorail'}];
    element.projectName = 'monorail';
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrGrid);
  });

  it('renders issues in ID mode', async () => {
    element.cellMode = 'IDs';

    await element.updateComplete;

    assert.instanceOf(element.shadowRoot.querySelector(
        'mr-issue-link'), MrIssueLink);
  });

  it('renders one issue in counts mode', async () => {
    element.cellMode = 'Counts';

    await element.updateComplete;

    const href = element.shadowRoot.querySelector('.counts').href;
    assert.include(href, '/p/monorail/issues/detail?id=1&x=&y=');
  });

  it('renders as tiles when invalid cell mode set', async () => {
    element.cellMode = 'InvalidCells';

    await element.updateComplete;

    const tile = element.shadowRoot.querySelector('mr-grid-tile');
    assert.isDefined(tile);
    assert.deepEqual(tile.issue, {localId: 1, projectName: 'monorail'});
  });

  it('sorts issues before rendering', async () => {
    const testIssue = {
      localId: 1,
      projectName: 'monorail',
      starCount: 2,
      blockedOnIssueRefs: [{localId: 22, projectName: 'chromium'}],
    };

    element.cellMode = 'Tiles';

    element.issues = [testIssue];
    element.xAttr = 'Stars';
    element.yAttr = 'Blocked';

    await element.updateComplete;

    assert.deepEqual(element.groupedIssues, new Map([
      ['2 + Yes', [testIssue]],
    ]));

    const rows = element.shadowRoot.querySelectorAll('tr');

    const colHeader = rows[0].querySelectorAll('th')[1];
    assert.equal(colHeader.textContent.trim(), '2');

    const rowHeader = rows[1].querySelector('th');
    assert.equal(rowHeader.textContent.trim(), 'Yes');

    const issueCell = rows[1].querySelector('td');
    const tile = issueCell.querySelector('mr-grid-tile');

    assert.isDefined(tile);
    assert.deepEqual(tile.issue, testIssue);
  });

  it('computes href for multiple items in counts mode', async () => {
    element.cellMode = 'Counts';

    element.issues = [
      {localId: 1, projectName: 'monorail'},
      {localId: 2, projectName: 'monorail'},
    ];

    await element.updateComplete;

    const href = element.shadowRoot.querySelector('.counts').href;
    assert.include(href, '/list?x=&y=&mode=');
  });

  it('computes counts link when grouped by row', async () => {
    await element.updateComplete;

    element.cellMode = 'Counts';
    element.queryParams = {x: 'Type', y: '', q: 'Type:Defect'};
    element.xHeadings = ['All', 'Defect'];
    element.yHeadings = ['All'];
    element.groupedIssues = new Map([
      ['All + All', [{'localId': 1, 'projectName': 'monorail'}]],
      ['Defect + All', [
        {localId: 2, projectName: 'monorail',
          labelRefs: [{label: 'Type-Defect'}]},
        {localId: 3, projectName: 'monorail',
          labelRefs: [{label: 'Type-Defect'}]},
      ]],
    ]);

    await element.updateComplete;

    const href = element.shadowRoot.querySelectorAll('.counts')[1].href;
    assert.include(href, '/list?x=Type&y=&q=Type%3ADefect&mode=');
  });

  it('computes counts link when grouped by col', async () => {
    await element.updateComplete;

    element.cellMode = 'Counts';
    element.queryParams = {x: '', y: 'Type', q: 'Type:Defect'};
    element.xHeadings = ['All'];
    element.yHeadings = ['All', 'Defect'];
    element.groupedIssues = new Map([
      ['All + All', [{'localId': 1, 'projectName': 'monorail'}]],
      ['All + Defect', [
        {localId: 2, projectName: 'monorail',
          labelRefs: [{label: 'Type-Defect'}]},
        {localId: 3, projectName: 'monorail',
          labelRefs: [{label: 'Type-Defect'}]},
      ]],
    ]);

    await element.updateComplete;

    const href = element.shadowRoot.querySelectorAll('.counts')[1].href;
    assert.include(href, '/list?x=&y=Type&q=Type%3ADefect&mode=');
  });

  it('computes counts link when grouped by row and col', async () => {
    await element.updateComplete;

    element.cellMode = 'Counts';
    element.queryParams = {x: 'Stars', y: 'Type',
      q: 'Type:Defect Stars=2'};
    element.xHeadings = ['All', '2'];
    element.yHeadings = ['All', 'Defect'];
    element.groupedIssues = new Map([
      ['All + All', [{'localId': 1, 'projectName': 'monorail'}]],
      ['2 + Defect', [
        {localId: 2, projectName: 'monorail',
          labelRefs: [{label: 'Type-Defect'}], starCount: 2},
        {localId: 3, projectName: 'monorail',
          labelRefs: [{label: 'Type-Defect'}], starCount: 2},
      ]],
    ]);

    await element.updateComplete;

    const href = element.shadowRoot.querySelectorAll('.counts')[1].href;
    assert.include(href,
        '/list?x=Stars&y=Type&q=Type%3ADefect%20Stars%3D2&mode=');
  });
});
