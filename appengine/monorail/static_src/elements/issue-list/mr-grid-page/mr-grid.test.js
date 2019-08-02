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
    element.queryParams = {'x': '', 'y': ''};
    element.projectName = 'monorail';
    element.groupedIssues = new Map();
    element.xHeadings = ['All'];
    element.yHeadings = ['All'];
    element.groupedIssues.set(
      'All + All', [{'localId': 1, 'projectName': 'monorail'}]
    );
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
    const startIndex = href.indexOf('/p');
    const trimmedHref = href.substring(startIndex);
    assert.equal(trimmedHref, '/p/monorail/issues/detail?id=1&x=&y=');
  });

  it('computes href for multiple items in counts mode', async () => {
    element.cellMode = 'Counts';

    const issues = element.groupedIssues.get('All + All');
    issues.push({'localId': 2, 'projectName': 'monorail'});
    element.groupedIssues.set('All + All', issues);

    await element.updateComplete;

    const href = element.shadowRoot.querySelector('.counts').href;
    const startIndex = href.indexOf('/list');
    const trimmedHref = href.substring(startIndex);
    assert.equal(trimmedHref, '/list?x=&y=&mode=');
  });

  it('computes href when grouped by row, counts', async () => {
    element.cellMode = 'Counts';
    element.queryParams = {'x': 'Type', 'y': '', 'q': 'Type:Defect'};
    element.xHeadings.push('Defect');
    const issues = [];
    issues.push({'localId': 2, 'projectName': 'monorail',
      'labelRefs': [{'label': 'Type-Defect'}]});
    issues.push({'localId': 3, 'projectName': 'monorail',
      'labelRefs': [{'label': 'Type-Defect'}]});
    element.groupedIssues.set('Defect + All', issues);

    await element.updateComplete;

    const href = element.shadowRoot.querySelectorAll('.counts')[1].href;
    const startIndex = href.indexOf('/list');
    const trimmedHref = href.substring(startIndex);
    assert.equal(trimmedHref, '/list?x=Type&y=&q=Type%3ADefect&mode=');
  });

  it('computes href when grouped by col, counts', async () => {
    element.cellMode = 'Counts';
    element.queryParams = {'x': '', 'y': 'Type', 'q': 'Type:Defect'};
    element.yHeadings.push('Defect');
    const issues = [];
    issues.push({'localId': 2, 'projectName': 'monorail',
      'labelRefs': [{'label': 'Type-Defect'}]});
    issues.push({'localId': 3, 'projectName': 'monorail',
      'labelRefs': [{'label': 'Type-Defect'}]});
    element.groupedIssues.set('All + Defect', issues);

    await element.updateComplete;

    const href = element.shadowRoot.querySelectorAll('.counts')[1].href;
    const startIndex = href.indexOf('/list');
    const trimmedHref = href.substring(startIndex);
    assert.equal(trimmedHref, '/list?x=&y=Type&q=Type%3ADefect&mode=');
  });

  it('computes href when grouped by row and col, counts', async () => {
    element.cellMode = 'Counts';
    element.queryParams = {'x': 'Stars', 'y': 'Type',
      'q': 'Type:Defect Stars=2'};
    element.xHeadings.push('2');
    element.yHeadings.push('Defect');
    const issues = [];
    issues.push({'localId': 2, 'projectName': 'monorail',
      'labelRefs': [{'label': 'Type-Defect'}], 'starCount': '2'});
    issues.push({'localId': 3, 'projectName': 'monorail',
      'labelRefs': [{'label': 'Type-Defect'}], 'starCount': '2'});
    element.groupedIssues.set('2 + Defect', issues);

    await element.updateComplete;

    const href = element.shadowRoot.querySelectorAll('.counts')[1].href;
    const startIndex = href.indexOf('/list');
    const trimmedHref = href.substring(startIndex);
    assert.equal(trimmedHref,
      '/list?x=Stars&y=Type&q=Type%3ADefect%20Stars%3D2&mode=');
  });
});
