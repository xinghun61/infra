// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '../../../bower_components/chopsui/tsmon-client.js';
const TSMonClient = window.chops.tsmon.TSMonClient;
import '../prpc.js';

const TS_MON_JS_PATH = '/_/jstsmon.do';
const TS_MON_CLIENT_GLOBAL_NAME = '__tsMonClient';
export const PAGE_TYPES = Object.freeze({
  ISSUE_DETAIL: 'issue_detail',
  ISSUE_LIST: 'issue_list',
});

export default class MonorailTSMon extends TSMonClient {

  constructor() {
    super(TS_MON_JS_PATH);
    this.clientId = MonorailTSMon.generateClientId();
    this.disableAfterNextFlush();
    // Create an instance of pRPC client for refreshing XSRF tokens.
    this.prpcClient = new window.__prpc.AutoRefreshPrpcClient(
      window.CS_env.token, window.CS_env.tokenExpiresSec);

    // TODO(jeffcarp, 4415): Deduplicate metric defs.
    const standardFields = new Map([
      ['client_id', TSMonClient.stringField('client_id')],
      ['host_name', TSMonClient.stringField('host_name')],
    ]);
    this._userTimingMetrics = [
      {
        category: 'issues',
        eventName: 'new-issue',
        metric: this.cumulativeDistribution(
          'monorail/frontend/issue_create_latency',
          'Latency between issue entry form submit and issue detail page load.',
          null, standardFields,
        ),
      },
      {
        category: 'issues',
        eventName: 'issue-update',
        metric: this.cumulativeDistribution(
          'monorail/frontend/issue_update_latency',
          'Latency between issue update form submit and issue detail page load.',
          null, standardFields,
        ),
      },
      {
        category: 'autocomplete',
        eventName: 'populate-options',
        metric: this.cumulativeDistribution(
          'monorail/frontend/autocomplete_populate_latency',
          'Latency between page load and autocomplete options loading.',
          null, standardFields,
        ),
      }
    ];

    this.pageLoadMetric = this.cumulativeDistribution(
      'frontend/dom_content_loaded',
      'domContentLoaded performance timing.',
      null, (new Map([
        ['client_id', TSMonClient.stringField('client_id')],
        ['host_name', TSMonClient.stringField('host_name')],
        ['template_name', TSMonClient.stringField('template_name')],
      ]))
    );
    this.recordPageLoadTiming();
  }

  fetchImpl(rawMetricValues) {
    return this.prpcClient.ensureTokenIsValid().then(() => {
      return fetch(this._reportPath, {
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          metrics: rawMetricValues,
          token: this.prpcClient.token,
        }),
      });
    });
  }

  recordUserTiming(category, eventName, elapsed) {
    const metricFields = new Map([
      ['client_id', this.clientId],
      ['host_name', window.CS_env.app_version],
    ]);
    for (let metric of this._userTimingMetrics) {
      if (category === metric.category
          && eventName === metric.eventName) {
        metric.metric.add(elapsed, metricFields);
      }
    }
  }

  recordPageLoadTiming() {
    // See timing definitions here:
    // https://developer.mozilla.org/en-US/docs/Web/API/PerformanceNavigationTiming
    const t = window.performance.timing;
    const domContentLoadedMs = t.domContentLoadedEventEnd - t.navigationStart;

    const measurePageTypes = new Set([
      PAGE_TYPES.ISSUE_LIST,
      PAGE_TYPES.ISSUE_DETAIL,
    ]);
    const pageType = MonorailTSMon.getPageTypeFromPath(window.location.pathname);
    if (measurePageTypes.has(pageType)) {
      const metricFields = new Map([
        ['client_id', this.clientId],
        ['host_name', window.CS_env.app_version],
        ['template_name', pageType],
      ]);
      this.pageLoadMetric.add(domContentLoadedMs, metricFields);
    }
  }

  // Returns an enum from PAGE_TYPES or null based on path.
  static getPageTypeFromPath(path) {
    const regexToPageType = {
      '/p/[A-Za-z0-9\-]+/issues/detail': PAGE_TYPES.ISSUE_DETAIL,
      '/p/[A-Za-z0-9\-]+/issues/list': PAGE_TYPES.ISSUE_LIST,
    };

    for (const [regex, pageType] of Object.entries(regexToPageType)) {
      if (path.match(regex)) {
        return pageType;
      }
    }

    return null;
  }

  // Uses the window object to ensure that only one ts_mon JS client
  // exists on the page at any given time. Returns the object on window,
  // instantiating it if it doesn't exist yet.
  static getGlobalClient() {
    const key = TS_MON_CLIENT_GLOBAL_NAME;
    if (!window.hasOwnProperty(key)) {
      window[key] = new MonorailTSMon();
    }
    return window[key];
  }

  static generateClientId() {
    /**
     * Returns a random string used as the client_id field in ts_mon metrics.
     *
     * Rationale:
     * If we assume Monorail has sustained 40 QPS, assume every request
     * generates a new ClientLogger (likely an overestimation), and we want
     * the likelihood of a client ID collision to be 0.01% for all IDs
     * generated in any given year (in other words, 1 collision every 10K
     * years), we need to generate a random string with at least 2^30 different
     * possible values (i.e. 30 bits of entropy, see log2(d) in Wolfram link
     * below). Using an unsigned integer gives us 32 bits of entropy, more than
     * enough.
     *
     * Returns:
     *   A string (the base-32 representation of a random 32-bit integer).

     * References:
     * - https://en.wikipedia.org/wiki/Birthday_problem
     * - https://www.wolframalpha.com/input/?i=d%3D40+*+60+*+60+*+24+*+365,+p%3D0.0001,+n+%3D+sqrt(2d+*+ln(1%2F(1-p))),+d,+log2(d),+n
     * - https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/toString
     */
    const randomvalues = new Uint32Array(1);
    window.crypto.getRandomValues(randomvalues);
    return randomvalues[0].toString(32);
  }
}
