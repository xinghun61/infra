// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {displayNameToUserRef, labelStringToRef, componentStringToRef,
  issueStringToRef, issueRefToString, fieldNameToLabelPrefix,
} from './converters.js';

describe('displayNameToUserRef', () => {
  it('converts displayName', () => {
    assert.deepEqual(displayNameToUserRef('foo'), {displayName: 'foo'});
  });
});

describe('labelStringToRef', () => {
  it('converts label', () => {
    assert.deepEqual(labelStringToRef('foo'), {label: 'foo'});
  });
});

describe('fieldNameToLabelPrefix', () => {
  it('converts fieldName', () => {
    assert.deepEqual(fieldNameToLabelPrefix('test'), 'test-');
    assert.deepEqual(fieldNameToLabelPrefix('test-hello'), 'test-hello-');
    assert.deepEqual(fieldNameToLabelPrefix('WHATEVER'), 'whatever-');
  });
});

describe('componentStringToRef', () => {
  it('converts component', () => {
    assert.deepEqual(componentStringToRef('foo'), {path: 'foo'});
  });
});

describe('issueStringToRef', () => {
  it('converts issue default project', () => {
    assert.deepEqual(
      issueStringToRef('proj', '1234'),
      {projectName: 'proj', localId: 1234});
  });

  it('converts issue with project', () => {
    assert.deepEqual(
      issueStringToRef('proj', 'foo:1234'),
      {projectName: 'foo', localId: 1234});
  });
});

describe('issueRefToString', () => {
  it('no ref', () => {
    assert.equal(issueRefToString(), '');
  });

  it('ref with no project name', () => {
    assert.equal(
      'other:1234',
      issueRefToString({projectName: 'other', localId: 1234})
    );
  });

  it('ref with different project name', () => {
    assert.equal(
      'other:1234',
      issueRefToString({projectName: 'other', localId: 1234}, 'proj')
    );
  });

  it('ref with same project name', () => {
    assert.equal(
      '1234',
      issueRefToString({projectName: 'proj', localId: 1234}, 'proj')
    );
  });
});
