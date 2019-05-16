// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {PrpcClient} from '@chopsui/prpc-client';

export const prpcClient = new PrpcClient ({
  insecure: Boolean(location.hostname === 'localhost'),
  fetchImpl: (url, options) => {
    options.credentials = 'same-origin';
    return fetch(url, options);
  },
});
