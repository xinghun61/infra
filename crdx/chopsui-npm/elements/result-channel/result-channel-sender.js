// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

export const TYPES = {
  RESULT: 'RESULT',
  ERROR: 'ERROR',
  DONE: 'DONE',
};

export class ResultChannelSender {
  constructor(name) {
    this._channel = new BroadcastChannel(name);
  }

  async send(asyncIterator) {
    try {
      for await (const payload of asyncIterator) {
        this._channel.postMessage({type: TYPES.RESULT, payload});
      }
    } catch (err) {
      this._channel.postMessage({type: TYPES.ERROR, payload: err.message});
    }
    this._channel.postMessage({type: TYPES.DONE});
    this._channel.close();
  }
}
