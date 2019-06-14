/* Copyright 2018 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import {TSMonClient} from '@chopsui/tsmon-client';

export const tsMonClient = new TSMonClient();
import AutoRefreshPrpcClient from 'prpc.js';

const TS_MON_JS_PATH = '/_/jstsmon.do';
const TS_MON_CLIENT_GLOBAL_NAME = '__tsMonClient';
const PAGE_LOAD_MAX_THRESHOLD = 60000;
export const PAGE_TYPES = Object.freeze({
  ISSUE_DETAIL: 'issue_detail',
  ISSUE_DETAIL_SPA: 'issue_detail_spa',
  ISSUE_LIST: 'issue_list',
});

export default class MonorailTSMon extends TSMonClient {
  constructor() {
    super(TS_MON_JS_PATH);
    this.clientId = MonorailTSMon.generateClientId();
    this.disableAfterNextFlush();
    // Create an instance of pRPC client for refreshing XSRF tokens.
    this.prpcClient = new AutoRefreshPrpcClient(
      window.CS_env.token, window.CS_env.tokenExpiresSec);

    // TODO(jeffcarp, 4415): Deduplicate metric defs.
    const standardFields = new Map([
      ['client_id', TSMonClient.stringField('client_id')],
      ['host_name', TSMonClient.stringField('host_name')],
      ['document_visible', TSMonClient.boolField('document_visible')],
    ]);
    this._userTimingMetrics = [
      {
        category: 'issues',
        eventName: 'new-issue',
        eventLabel: 'server-time',
        metric: this.cumulativeDistribution(
          'monorail/frontend/issue_create_latency',
          'Latency between issue entry form submit and issue detail page load.',
          null, standardFields,
        ),
      },
      {
        category: 'issues',
        eventName: 'issue-update',
        eventLabel: 'computer-time',
        metric: this.cumulativeDistribution(
          'monorail/frontend/issue_update_latency',
          'Latency between issue update form submit and issue detail page load.',
          null, standardFields,
        ),
      },
      {
        category: 'autocomplete',
        eventName: 'populate-options',
        eventLabel: 'user-time',
        metric: this.cumulativeDistribution(
          'monorail/frontend/autocomplete_populate_latency',
          'Latency between page load and autocomplete options loading.',
          null, standardFields,
        ),
      },
    ];

    this.dateRangeMetric = this.counter(
      'monorail/frontend/charts/switch_date_range',
      'Number of times user changes date range.',
      null, (new Map([
        ['client_id', TSMonClient.stringField('client_id')],
        ['host_name', TSMonClient.stringField('host_name')],
        ['document_visible', TSMonClient.boolField('document_visible')],
        ['date_range', TSMonClient.intField('date_range')],
      ]))
    );

    this.issueCommentsLoadMetric = this.cumulativeDistribution(
      'monorail/frontend/issue_comments_load_latency',
      'Time from navigation or click to issue comments loaded.',
      null, (new Map([
        ['client_id', TSMonClient.stringField('client_id')],
        ['host_name', TSMonClient.stringField('host_name')],
        ['template_name', TSMonClient.stringField('template_name')],
        ['document_visible', TSMonClient.boolField('document_visible')],
        ['full_app_load', TSMonClient.boolField('full_app_load')],
      ]))
    );

    this.pageLoadMetric = this.cumulativeDistribution(
      'frontend/dom_content_loaded',
      'domContentLoaded performance timing.',
      null, (new Map([
        ['client_id', TSMonClient.stringField('client_id')],
        ['host_name', TSMonClient.stringField('host_name')],
        ['template_name', TSMonClient.stringField('template_name')],
        ['document_visible', TSMonClient.boolField('document_visible')],
      ]))
    );
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

  recordUserTiming(category, eventName, eventLabel, elapsed) {
    const metricFields = new Map([
      ['client_id', this.clientId],
      ['host_name', window.CS_env.app_version],
      ['document_visible', MonorailTSMon.isPageVisible()],
    ]);
    for (const metric of this._userTimingMetrics) {
      if (category === metric.category
          && eventName === metric.eventName
          && eventLabel === metric.eventLabel) {
        metric.metric.add(elapsed, metricFields);
      }
    }
  }

  recordDateRangeChange(dateRange) {
    const metricFields = new Map([
      ['client_id', this.clientId],
      ['host_name', window.CS_env.app_version],
      ['document_visible', MonorailTSMon.isPageVisible()],
      ['date_range', dateRange],
    ]);
    this.dateRangeMetric.add(1, metricFields);
  }

  // Make sure this function runs after the page is loaded.
  recordPageLoadTiming(pageType, maxThresholdMs=null) {
    if (!pageType) return;
    // See timing definitions here:
    // https://developer.mozilla.org/en-US/docs/Web/API/PerformanceNavigationTiming
    const t = window.performance.timing;
    const domContentLoadedMs = t.domContentLoadedEventEnd - t.navigationStart;

    const measurePageTypes = new Set([
      PAGE_TYPES.ISSUE_LIST,
      PAGE_TYPES.ISSUE_DETAIL,
      PAGE_TYPES.ISSUE_DETAIL_SPA,
    ]);

    if (measurePageTypes.has(pageType)) {
      if (maxThresholdMs !== null && domContentLoadedMs > maxThresholdMs) {
        return;
      }
      const metricFields = new Map([
        ['client_id', this.clientId],
        ['host_name', window.CS_env.app_version],
        ['template_name', pageType],
        ['document_visible', MonorailTSMon.isPageVisible()],
      ]);
      this.pageLoadMetric.add(domContentLoadedMs, metricFields);
    }
  }

  recordIssueCommentsLoadTiming(value, fullAppLoad) {
    const metricFields = new Map([
      ['client_id', this.clientId],
      ['host_name', window.CS_env.app_version],
      ['template_name', PAGE_TYPES.ISSUE_DETAIL_SPA],
      ['document_visible', MonorailTSMon.isPageVisible()],
      ['full_app_load', fullAppLoad],
    ]);
    this.issueCommentsLoadMetric.add(value, metricFields);
  }

  recordIssueDetailTiming(maxThresholdMs=PAGE_LOAD_MAX_THRESHOLD) {
    this.recordPageLoadTiming(PAGE_TYPES.ISSUE_DETAIL, maxThresholdMs);
  }

  recordIssueDetailSpaTiming(maxThresholdMs=PAGE_LOAD_MAX_THRESHOLD) {
    this.recordPageLoadTiming(PAGE_TYPES.ISSUE_DETAIL_SPA, maxThresholdMs);
  }

  recordIssueListTiming(maxThresholdMs=PAGE_LOAD_MAX_THRESHOLD) {
    this.recordPageLoadTiming(PAGE_TYPES.ISSUE_LIST, maxThresholdMs);
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

  // Returns a Boolean, true if document is visible.
  static isPageVisible(path) {
    return document.visibilityState === 'visible';
  }
}

// For integration with EZT pages, which don't use ES modules.
window.getTSMonClient = MonorailTSMon.getGlobalClient;
