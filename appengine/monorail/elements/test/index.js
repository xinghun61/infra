// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// TODO(zhangtiff): Remove these separate checks once element
//   directories are merged.
const testsContext = require.context('../../elements', true, /\.test\.js$/);
const testsContext2 = require.context('../../static', true, /\.test\.js$/);
testsContext.keys().forEach(testsContext);
testsContext2.keys().forEach(testsContext2);
