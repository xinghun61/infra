// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {TYPES} from './result-channel-sender.js';

export class ResultChannelReceiver {
  constructor(name) {
    this._messageQueue = [];
    this._onMessage = undefined;
    this._handleMessage = this._handleMessage.bind(this);
    this._channel = new BroadcastChannel(name);
    this._channel.addEventListener('message', this._handleMessage);
  }

  _handleMessage({data}) {
    this._messageQueue.push(data);
    if (this._onMessage) this._onMessage();
  }

  async next() {
    if (this._messageQueue.length === 0) {
      await new Promise((resolve) => {
        this._onMessage = resolve;
      });
      this._onMessage = undefined;
    }
    const {type, payload} = this._messageQueue.shift();
    switch (type) {
      case TYPES.RESULT:
        return {done: false, value: payload};

      case TYPES.ERROR:
        throw new Error(payload);

      case TYPES.DONE:
        this._channel.removeEventListener('message', this._handleMessage);
        this._channel.close();
        return {done: true};

      default:
        throw new Error(`Unknown message type: ${type}`);
    }
  }

  [Symbol.asyncIterator]() {
    return this;
  }
}
