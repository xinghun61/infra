// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrCommentContent} from './mr-comment-content.js';


let element;

describe('mr-comment-content', () => {
  beforeEach(() => {
    element = document.createElement('mr-comment-content');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrCommentContent);
  });

  it('does not render spurious spaces', async () => {
    element.content =
      'Some text before a go/link and more text before <b>some bold text</b>.';

    await element.updateComplete;

    const textContents = Array.from(element.shadowRoot.children).map(
        (child) => child.textContent);

    assert.deepEqual(textContents, [
      'Some text before a',
      ' ',
      'go/link',
      ' and more text before ',
      'some bold text',
      '.',
    ]);

    assert.deepEqual(
        element.shadowRoot.textContent,
        'Some text before a go/link and more text before some bold text.');
  });
});
