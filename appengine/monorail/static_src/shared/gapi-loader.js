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

const BUGANIZER_SCOPE = 'https://www.googleapis.com/auth/buganizer';
// Only allow google.com profiles through currently.
const RESTRICT_TO_DOMAIN = '@google.com';

// loadGapi loads window.gapi and returns a logged in user object or null.
// Allows overriding signinImpl for testing.
export default function loadGapi(signinImpl=signin) {
  // Validate client_id exists.
  if (!CS_env.gapi_client_id) {
    throw new Error('Cannot find gapi.js client id');
  }

  // Prevent gapi.js from being loaded multiple times.
  if (window.__gapiLoadPromise) {
    return window.__gapiLoadPromise;
  }

  window.__gapiLoadPromise = new Promise(async (resolve) => {
    signinImpl.init(CS_env.gapi_client_id, ['client'], [BUGANIZER_SCOPE]);
    resolve(await fetchGapiEmail(signinImpl));
  });

  return window.__gapiLoadPromise;
}

// For fetching current email. May have changed since load.
export function fetchGapiEmail(signinImpl=signin) {
  return new Promise((resolve) => {
    signinImpl.getUserProfileAsync().then((profile) => {
      resolve(
          (
            profile
            && profile.getEmail instanceof Function
            && profile.getEmail().endsWith(RESTRICT_TO_DOMAIN)
            && profile.getEmail()
          ) || null
      );
    });
  });
}
