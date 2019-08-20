// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {store} from 'reducers/base.js';
import * as sitewide from 'reducers/sitewide.js';

// How long should we wait until asking the server status again.
const SERVER_STATUS_DELAY_MS = 20 * 60 * 1000; // 20 minutes

// CronTask is a class that supports periodically execution of tasks.
export class CronTask {
  constructor(task, delay) {
    this.task = task;
    this.delay = delay;
    this.started = false;
  }

  start() {
    if (this.started) return;
    this.started = true;
    this._execute();
  }

  _execute() {
    this.task();
    setTimeout(this._execute.bind(this), this.delay);
  }
}

// getServerStatusCron requests status information from the server every 20
// minutes.
export const getServerStatusCron = new CronTask(
    () => store.dispatch(sitewide.getServerStatus()),
    SERVER_STATUS_DELAY_MS);
