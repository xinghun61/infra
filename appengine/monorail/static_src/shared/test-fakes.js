// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';

export const clientLoggerFake = () => ({
  logStart: sinon.stub(),
  logEnd: sinon.stub(),
  logPause: sinon.stub(),
  started: sinon.stub().returns(true),
});
