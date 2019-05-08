// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrMetadata} from './mr-metadata.js';


let element;

describe('mr-metadata', () => {
  beforeEach(() => {
    element = document.createElement('mr-metadata');
    document.body.appendChild(element);

    element.projectName = 'proj';
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrMetadata);
  });
});
