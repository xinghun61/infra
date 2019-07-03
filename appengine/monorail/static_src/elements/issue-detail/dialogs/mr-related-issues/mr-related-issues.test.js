// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrRelatedIssues} from './mr-related-issues.js';


let element;

describe('mr-related-issues', () => {
  beforeEach(() => {
    element = document.createElement('mr-related-issues');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrRelatedIssues);
  });

  it('computes blocked on table rows', () => {
    element.projectName = 'proj';
    element.sortedBlockedOn = [
      {projectName: 'proj', localId: 1, statusRef: {meansOpen: true},
        summary: 'Issue 1'},
      {projectName: 'proj', localId: 2, statusRef: {meansOpen: true},
        summary: 'Issue 2'},
      {projectName: 'proj', localId: 3,
        summary: 'Issue 3'},
      {projectName: 'proj2', localId: 4,
        summary: 'Issue 4 on another project'},
      {projectName: 'proj', localId: 5, statusRef: {meansOpen: false},
        summary: 'Issue 5'},
      {projectName: 'proj2', localId: 6, statusRef: {meansOpen: false},
        summary: 'Issue 6 on another project'},
    ];
    assert.deepEqual(element._rows, [
      {
        draggable: true,
        cells: [
          {
            type: 'issue',
            issue: {projectName: 'proj', localId: 1, statusRef: {meansOpen: true},
              summary: 'Issue 1'},
            isClosed: false,
          },
          {
            type: 'text',
            content: 'Issue 1',
          },
        ],
      },
      {
        draggable: true,
        cells: [
          {
            type: 'issue',
            issue: {projectName: 'proj', localId: 2, statusRef: {meansOpen: true},
              summary: 'Issue 2'},
            isClosed: false,
          },
          {
            type: 'text',
            content: 'Issue 2',
          },
        ],
      },
      {
        draggable: true,
        cells: [
          {
            type: 'issue',
            issue: {projectName: 'proj', localId: 3,
              summary: 'Issue 3'},
            isClosed: false,
          },
          {
            type: 'text',
            content: 'Issue 3',
          },
        ],
      },
      {
        draggable: true,
        cells: [
          {
            type: 'issue',
            issue: {projectName: 'proj2', localId: 4,
              summary: 'Issue 4 on another project'},
            isClosed: false,
          },
          {
            type: 'text',
            content: 'Issue 4 on another project',
          },
        ],
      },
      {
        draggable: false,
        cells: [
          {
            type: 'issue',
            issue: {projectName: 'proj', localId: 5,
              statusRef: {meansOpen: false},
              summary: 'Issue 5'},
            isClosed: true,
          },
          {
            type: 'text',
            content: 'Issue 5',
          },
        ],
      },
      {
        draggable: false,
        cells: [
          {
            type: 'issue',
            issue: {projectName: 'proj2', localId: 6,
              statusRef: {meansOpen: false},
              summary: 'Issue 6 on another project'},
            isClosed: true,
          },
          {
            type: 'text',
            content: 'Issue 6 on another project',
          },
        ],
      },
    ]);
  });
});
