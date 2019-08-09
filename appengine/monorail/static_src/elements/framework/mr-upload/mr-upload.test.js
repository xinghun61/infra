// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrUpload} from './mr-upload.js';

let element;
let preventDefault;
let mockEvent;


describe('mr-upload', () => {
  beforeEach(() => {
    element = document.createElement('mr-upload');
    document.body.appendChild(element);

    preventDefault = sinon.stub();

    mockEvent = (properties) => {
      return Object.assign({
        preventDefault: preventDefault,
      }, properties);
    };
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrUpload);
  });

  it('reset clears files', () => {
    element.files = [new File([''], 'filename.txt'), new File([''], 'hello')];

    element.reset();

    assert.deepEqual(element.files, []);
  });

  it('editing file selector adds files', () => {
    const files = [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
    ];
    assert.deepEqual(element.files, []);

    // NOTE: There is currently no way to use JavaScript to set the value of
    // an HTML file input.

    element._filesChanged({
      currentTarget: {
        files: files,
      },
    });

    assert.deepEqual(element.files, files);
  });

  it('files are rendered', async () => {
    element.files = [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
      new File([''], 'file.png'),
    ];

    await element.updateComplete;

    const items = element.shadowRoot.querySelectorAll('li');

    assert.equal(items.length, 3);

    assert.include(items[0].textContent, 'filename.txt');
    assert.include(items[1].textContent, 'hello');
    assert.include(items[2].textContent, 'file.png');
  });

  it('clicking removes file', async () => {
    element.files = [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
      new File([''], 'file.png'),
    ];

    await element.updateComplete;

    let items = element.shadowRoot.querySelectorAll('li');

    assert.equal(items.length, 3);

    items[1].querySelector('button').click();

    await element.updateComplete;

    items = element.shadowRoot.querySelectorAll('li');

    assert.equal(items.length, 2);

    assert.include(items[0].textContent, 'filename.txt');
    assert.include(items[1].textContent, 'file.png');

    // Make sure clicking works even for children targets.
    items[0].querySelector('i.material-icons').click();

    await element.updateComplete;

    items = element.shadowRoot.querySelectorAll('li');

    assert.equal(items.length, 1);

    assert.include(items[0].textContent, 'file.png');
  });

  it('duplicate files are ignored', () => {
    const file1 = new File([''], 'filename.txt');
    const file2 = new File([''], 'woahhh');
    const file3 = new File([''], 'filename');

    element.files = [file1, file2];

    element._addFiles([file2, file3]);

    assert.deepEqual(element.files, [file1, file2, file3]);
  });

  it('dragging file into window expands element', () => {
    assert.isFalse(element.expanded);
    assert.deepEqual(element.files, []);

    element._onDragIntoWindow(mockEvent({dataTransfer: {files: [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
    ]}}));

    assert.isTrue(element.expanded);
    assert.deepEqual(element.files, []);
    assert.isTrue(preventDefault.calledOnce);

    element._onDragOutOfWindow(mockEvent({dataTransfer: {files: [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
    ]}}));

    assert.isFalse(element.expanded);
    assert.deepEqual(element.files, []);
    assert.isTrue(preventDefault.calledTwice);
  });

  it('dragging non-file into window does not expands element', () => {
    assert.isFalse(element.expanded);

    element._onDragIntoWindow(mockEvent(
        {dataTransfer: {files: [], items: [{kind: 'notFile'}]}}
    ));

    assert.isFalse(element.expanded);
    assert.isFalse(preventDefault.called);

    element._onDragOutOfWindow(mockEvent(
        {dataTransfer: {files: [], items: [{kind: 'notFile'}]}}
    ));

    assert.isFalse(element.expanded);
    assert.isFalse(preventDefault.called);
  });

  it('dragging file over element highlights it', () => {
    assert.isFalse(element.highlighted);
    assert.deepEqual(element.files, []);

    element._onDragInto(mockEvent({dataTransfer: {files: [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
    ]}}));

    assert.isTrue(element.highlighted);
    assert.deepEqual(element.files, []);
    assert.isTrue(preventDefault.calledOnce);

    element._onDragLeave(mockEvent({dataTransfer: {files: [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
    ]}}));

    assert.isFalse(element.highlighted);
    assert.deepEqual(element.files, []);
    assert.isTrue(preventDefault.calledTwice);
  });

  it('dropping file over element selects it', () => {
    const files = [
      new File([''], 'filename.txt'),
      new File([''], 'hello'),
    ];
    assert.deepEqual(element.files, []);

    element._onDrop(mockEvent({dataTransfer: {files: files}}));

    assert.isTrue(preventDefault.calledOnce);
    assert.deepEqual(element.files, files);
  });

  it('loadFiles loads files', async () => {
    element.files = [
      new File(['some content'], 'filename.txt'),
      new File([''], 'hello'),
    ];

    const uploads = await element.loadFiles();

    assert.deepEqual(uploads, [
      {content: 'c29tZSBjb250ZW50', filename: 'filename.txt'},
      {content: '', filename: 'hello'},
    ]);
  });
});
