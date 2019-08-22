// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * gapi-loader.js provides a method for loading gapi.js asynchronously.
 *
 * gapi.js docs:
 * https://developers.google.com/identity/sign-in/web/reference
 * (we load gapi.js via the chops-signin module)
 */

import * as signin from '@chopsui/chops-signin';

// loadGapi loads window.gapi and returns a logged in user object or null.
export default async function loadGapi() {
  // Prevent gapi.js from being loaded multiple times.
  if (window.__gapiLoadStarted) {
    return;
  }
  window.__gapiLoadStarted = true;

  if (!CS_env.gapi_client_id) {
    throw new Error('Cannot find gapi.js client id');
  }

  signin.init(CS_env.gapi_client_id);
  return await signin.getUserProfileAsync();
}
