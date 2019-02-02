/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import {assert} from 'chai';
import {MrMetadata} from './mr-metadata.js';


let element;

suite('mr-metadata');

beforeEach(() => {
  element = document.createElement('mr-metadata');
  document.body.appendChild(element);

  element.projectName = 'proj';
  element.blockerReferences = new Map([
    [
      'proj:1', {
        issue: {summary: 'Issue 1'},
      },
    ],
    [
      'proj:2', {
        issue: {summary: 'Issue 2'},
        isClosed: true,
      },
    ],
    [
      'proj:3', {
        issue: {summary: 'Issue 3'},
      },
    ],
    [
      'proj2:4', {
        issue: {summary: 'Issue 4 on another project'},
        isClosed: true,
      },
    ],
    [
      'proj:5', {
        issue: {summary: 'Issue 5'},
      },
    ],
    [
      'proj2:6', {
        issue: {summary: 'Issue 6 on another project'},
      },
    ],
  ]);
  element.blockedOn = [
    {projectName: 'proj', localId: 1},
    {projectName: 'proj', localId: 2},
    {projectName: 'proj', localId: 3},
    {projectName: 'proj2', localId: 4},
    {projectName: 'proj', localId: 5},
    {projectName: 'proj2', localId: 6},
  ];
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, MrMetadata);
});

test('sorts blocked on', () => {
  assert.deepEqual(element.sortedBlockedOn, [
    {projectName: 'proj', localId: 1},
    {projectName: 'proj', localId: 3},
    {projectName: 'proj', localId: 5},
    {projectName: 'proj2', localId: 6},
    {projectName: 'proj', localId: 2},
    {projectName: 'proj2', localId: 4},
  ]);
});

test('computes blocked on table rows', () => {
  assert.deepEqual(element.blockedOnTableRows, [
    {
      draggable: true,
      cells: [
        {
          type: 'issue',
          projectName: 'proj',
          issue: {summary: 'Issue 1'},
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
          projectName: 'proj',
          issue: {summary: 'Issue 3'},
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
          projectName: 'proj',
          issue: {summary: 'Issue 5'},
          isClosed: false,
        },
        {
          type: 'text',
          content: 'Issue 5',
        },
      ],
    },
    {
      draggable: true,
      cells: [
        {
          type: 'issue',
          projectName: 'proj',
          issue: {summary: 'Issue 6 on another project'},
          isClosed: false,
        },
        {
          type: 'text',
          content: 'Issue 6 on another project',
        },
      ],
    },
    {
      draggable: false,
      cells: [
        {
          type: 'issue',
          projectName: 'proj',
          issue: {summary: 'Issue 2'},
          isClosed: true,
        },
        {
          type: 'text',
          content: 'Issue 2',
        },
      ],
    },
    {
      draggable: false,
      cells: [
        {
          type: 'issue',
          projectName: 'proj',
          issue: {summary: 'Issue 4 on another project'},
          isClosed: true,
        },
        {
          type: 'text',
          content: 'Issue 4 on another project',
        },
      ],
    },
  ]);
});
