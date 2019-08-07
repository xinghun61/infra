// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import {MrGridTile} from './mr-grid-tile.js';

let element;
const summary = 'Testing summary of an issue.';
const testIssue = {
  projectName: 'Monorail',
  localId: '2345',
  summary: summary,
};

describe('mr-grid-tile', () => {
  beforeEach(() => {
    element = document.createElement('mr-grid-tile');
    element.issue = testIssue;
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrGridTile);
  });

  it('properly links', async () => {
    await element.updateComplete;
    const tileLink = element.shadowRoot.querySelector('a').getAttribute('href');
    assert.equal(tileLink, `/p/Monorail/issues/detail?id=2345`);
  });

  it('summary displays', async () => {
    await element.updateComplete;
    const tileSummary =
      element.shadowRoot.querySelector('.summary').textContent;
    assert.equal(tileSummary.trim(), summary);
  });

  it('status displays', async () => {
    await element.updateComplete;
    const tileStatus =
      element.shadowRoot.querySelector('.status').textContent;
    assert.equal(tileStatus.trim(), '');
  });

  it('id displays', async () => {
    await element.updateComplete;
    const tileId =
      element.shadowRoot.querySelector('.issue-id').textContent;
    assert.equal(tileId.trim(), '2345');
  });
});
