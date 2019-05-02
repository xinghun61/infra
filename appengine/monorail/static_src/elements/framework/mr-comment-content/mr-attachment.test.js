// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert, expect} from 'chai';
import {MrAttachment} from './mr-attachment.js';
import sinon from 'sinon';


let element;

suite('mr-comment-content', () => {
  setup(() => {
    element = document.createElement('mr-attachment');
    document.body.appendChild(element);

    sinon.stub(window.prpcClient, 'call').callsFake(
      () => Promise.resolve({}));
  });

  teardown(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, MrAttachment);
  });

  test('shows image thumbnail', async () => {
    element.attachment = {
      thumbnailUrl: 'thumbnail.jpeg',
      contentType: 'image/jpeg',
    };
    await element.updateComplete;
    const img = element.shadowRoot.querySelector('img');
    assert.isNotNull(img);
    assert.isTrue(img.src.endsWith('thumbnail.jpeg'));
  });

  test('shows video thumbnail', async () => {
    element.attachment = {
      viewUrl: 'video.mp4',
      contentType: 'video/mpeg',
    };
    await element.updateComplete;
    const video = element.shadowRoot.querySelector('video');
    assert.isNotNull(video);
    assert.isTrue(video.src.endsWith('video.mp4'));
  });

  test('does not show image thumbnail if deleted', async () => {
    element.attachment = {
      thumbnailUrl: 'thumbnail.jpeg',
      contentType: 'image/jpeg',
      isDeleted: true,
    };
    await element.updateComplete;
    const img = element.shadowRoot.querySelector('img');
    assert.isNull(img);
  });

  test('does not show video thumbnail if deleted', async () => {
    element.attachment = {
      viewUrl: 'video.mp4',
      contentType: 'video/mpeg',
      isDeleted: true,
    };
    await element.updateComplete;
    const video = element.shadowRoot.querySelector('video');
    assert.isNull(video);
  });

  test('deletes attachment', async () => {
    element.attachment = {
      attachmentId: 67890,
      isDeleted: false,
    };
    element.canDelete = true;
    element.projectName = 'proj';
    element.localId = 1234;
    element.sequenceNum = 3;
    await element.updateComplete;

    const deleteButton = element.shadowRoot.querySelector('chops-button');
    deleteButton.click();

    assert.deepEqual(window.prpcClient.call.getCall(0).args, [
      'monorail.Issues', 'DeleteAttachment',
      {
        issueRef: {
          projectName: 'proj',
          localId: 1234,
        },
        sequenceNum: 3,
        attachmentId: 67890,
        delete: true,
      },
    ]);
    assert.isTrue(window.prpcClient.call.calledOnce);
  });

  test('undeletes attachment', async () => {
    element.attachment = {
      attachmentId: 67890,
      isDeleted: true,
    };
    element.canDelete = true;
    element.projectName = 'proj';
    element.localId = 1234;
    element.sequenceNum = 3;
    await element.updateComplete;

    const deleteButton = element.shadowRoot.querySelector('chops-button');
    deleteButton.click();

    assert.deepEqual(window.prpcClient.call.getCall(0).args, [
      'monorail.Issues', 'DeleteAttachment',
      {
        issueRef: {
          projectName: 'proj',
          localId: 1234,
        },
        sequenceNum: 3,
        attachmentId: 67890,
        delete: false,
      },
    ]);
    assert.isTrue(window.prpcClient.call.calledOnce);
  });

  test('view link is not displayed if not given', async () => {
    element.attachment = {};
    await element.updateComplete;
    const viewLink = element.shadowRoot.querySelector('#view-link');
    assert.isNotNull(viewLink);
    expect(viewLink).be.hidden;
  });

  test('view link is displayed if given', async () => {
    element.attachment = {
      viewUrl: 'http://example.com/attachment.foo',
    };
    await element.updateComplete;
    const viewLink = element.shadowRoot.querySelector('#view-link');
    assert.isNotNull(viewLink);
    expect(viewLink).be.visible;
    assert.equal(viewLink.href, 'http://example.com/attachment.foo');
  });

  test('download link is not displayed if not given', async () => {
    element.attachment = {};
    await element.updateComplete;
    const downloadLink = element.shadowRoot.querySelector('#download-link');
    assert.isNotNull(downloadLink);
    expect(downloadLink).be.hidden;
  });

  test('download link is displayed if given', async () => {
    element.attachment = {
      downloadUrl: 'http://example.com/attachment.foo',
    };
    await element.updateComplete;
    const downloadLink = element.shadowRoot.querySelector('#download-link');
    assert.isNotNull(downloadLink);
    expect(downloadLink).be.visible;
    assert.equal(downloadLink.href, 'http://example.com/attachment.foo');
  });
});
