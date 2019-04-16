// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {displayNameToUserRef, labelStringToRef, componentStringToRef,
  issueStringToRef, issueRefToString, fieldNameToLabelPrefix,
} from './converters.js';

suite('displayNameToUserRef', () => {
  test('converts displayName', () => {
    assert.deepEqual(displayNameToUserRef('foo'), {displayName: 'foo'});
  });
});

suite('labelStringToRef', () => {
  test('converts label', () => {
    assert.deepEqual(labelStringToRef('foo'), {label: 'foo'});
  });
});

suite('fieldNameToLabelPrefix', () => {
  test('converts fieldName', () => {
    assert.deepEqual(fieldNameToLabelPrefix('test'), 'test-');
    assert.deepEqual(fieldNameToLabelPrefix('test-hello'), 'test-hello-');
    assert.deepEqual(fieldNameToLabelPrefix('WHATEVER'), 'whatever-');
  });
});

suite('componentStringToRef', () => {
  test('converts component', () => {
    assert.deepEqual(componentStringToRef('foo'), {path: 'foo'});
  });
});

suite('issueStringToRef', () => {
  test('converts issue default project', () => {
    assert.deepEqual(
      issueStringToRef('proj', '1234'),
      {projectName: 'proj', localId: 1234});
  });

  test('converts issue with project', () => {
    assert.deepEqual(
      issueStringToRef('proj', 'foo:1234'),
      {projectName: 'foo', localId: 1234});
  });
});

suite('issueRefToString', () => {
  test('no ref', () => {
    assert.equal(issueRefToString(), '');
  });

  test('ref with no project name', () => {
    assert.equal(
      'other:1234',
      issueRefToString({projectName: 'other', localId: 1234})
    );
  });

  test('ref with different project name', () => {
    assert.equal(
      'other:1234',
      issueRefToString({projectName: 'other', localId: 1234}, 'proj')
    );
  });

  test('ref with same project name', () => {
    assert.equal(
      '1234',
      issueRefToString({projectName: 'proj', localId: 1234}, 'proj')
    );
  });
});
