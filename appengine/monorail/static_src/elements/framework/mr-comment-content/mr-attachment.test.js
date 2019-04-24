// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert, expect} from 'chai';
import {MrAttachment} from './mr-attachment.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


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

  test('shows image thumbnail', () => {
    element.attachment = {
      thumbnailUrl: 'thumbnail.jpeg',
      contentType: 'image/jpeg',
    };
    flush();
    const img = element.shadowRoot.querySelector('img');
    assert.isNotNull(img);
    assert.isTrue(img.src.endsWith('thumbnail.jpeg'));
  });

  test('shows video thumbnail', () => {
    element.attachment = {
      viewUrl: 'video.mp4',
      contentType: 'video/mpeg',
    };
    flush();
    const video = element.shadowRoot.querySelector('video');
    assert.isNotNull(video);
    assert.isTrue(video.src.endsWith('video.mp4'));
  });

  test('does not show image thumbnail if deleted', () => {
    element.attachment = {
      thumbnailUrl: 'thumbnail.jpeg',
      contentType: 'image/jpeg',
      isDeleted: true,
    };
    flush();
    const img = element.shadowRoot.querySelector('img');
    assert.isNull(img);
  });

  test('does not show video thumbnail if deleted', () => {
    element.attachment = {
      viewUrl: 'video.mp4',
      contentType: 'video/mpeg',
      isDeleted: true,
    };
    flush();
    const video = element.shadowRoot.querySelector('video');
    assert.isNull(video);
  });

  test('deletes attachment', () => {
    element.attachment = {
      attachmentId: 67890,
      isDeleted: false,
    };
    element.canDelete = true;
    element.projectName = 'proj';
    element.localId = 1234;
    element.sequenceNum = 3;
    flush();

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

  test('undeletes attachment', () => {
    element.attachment = {
      attachmentId: 67890,
      isDeleted: true,
    };
    element.canDelete = true;
    element.projectName = 'proj';
    element.localId = 1234;
    element.sequenceNum = 3;
    flush();

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

  test('view link is not displayed if not given', () => {
    element.attachment = {};
    flush();
    const viewLink = element.shadowRoot.querySelector('#view-link');
    assert.isNotNull(viewLink);
    expect(viewLink).be.hidden;
  });

  test('view link is displayed if given', () => {
    element.attachment = {
      viewUrl: 'http://example.com/attachment.foo',
    };
    flush();
    const viewLink = element.shadowRoot.querySelector('#view-link');
    assert.isNotNull(viewLink);
    expect(viewLink).be.visible;
    assert.equal(viewLink.href, 'http://example.com/attachment.foo');
  });

  test('download link is not displayed if not given', () => {
    element.attachment = {};
    flush();
    const downloadLink = element.shadowRoot.querySelector('#download-link');
    assert.isNotNull(downloadLink);
    expect(downloadLink).be.hidden;
  });

  test('download link is displayed if given', () => {
    element.attachment = {
      downloadUrl: 'http://example.com/attachment.foo',
    };
    flush();
    const downloadLink = element.shadowRoot.querySelector('#download-link');
    assert.isNotNull(downloadLink);
    expect(downloadLink).be.visible;
    assert.equal(downloadLink.href, 'http://example.com/attachment.foo');
  });
});
