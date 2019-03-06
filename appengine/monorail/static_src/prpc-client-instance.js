// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import AutoRefreshPrpcClient from './prpc.js';

export const prpcClient = new AutoRefreshPrpcClient(
  window.CS_env ? window.CS_env.token : '',
  window.CS_env ? window.CS_env.tokenExpiresSec : 0
);
