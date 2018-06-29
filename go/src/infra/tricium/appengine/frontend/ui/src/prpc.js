// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use script';

// TODO(qyearsley):
// Consider replacing this with prpc-client.js in chopsui.

/**
 * Makes a JSON pRPC request to the server.
 *
 * @param {string} method pRPC method name.
 * @param {Object} body pRPC request body.
 *
 * Resolves to a parsed object on success response.
 * Rejects to an error with response text on failure.
 */
async function request(method, body) {
  const url = `/prpc/tricium.Tricium/${method}`;
  const headers = new Headers({
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  });
  const opts = {
    headers,
    method: 'POST',
    body: JSON.stringify(body),
  };
  const response = await fetch(url, opts);
  try {
    return await _parseRpcJson(response);
  } catch (error) {
    return error;
  }
}

async function _parseRpcJson(response) {
  const jsonPrefix = ')]}\'';
  const text = await response.text();
  if (!text.startsWith(jsonPrefix)) {
    throw Error('Got response text:' + text);
  }
  return JSON.parse(text.substring(jsonPrefix.length));
}

export {request};
