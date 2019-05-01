// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import moment from 'moment';
import '@chopsui/chops-login/index.js';
import '@polymer/app-layout/app-header/app-header.js';
import '@polymer/app-layout/app-toolbar/app-toolbar.js';
import '@polymer/app-layout/app-scroll-effects/app-scroll-effects.js';
import '@polymer/app-layout/app-scroll-effects/effects/waterfall.js';
import '@polymer/iron-ajax/iron-ajax.js';
import {timeOut} from '@polymer/polymer/lib/utils/async.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

import 'last-updated-message.js';
import 'tree-status.js';
import 'status-table.js';


/**
 * `<chopsdash-app>`
 *
 * Base page for chopsdash.
 *
 **/
export class ChopsdashApp extends PolymerElement {
  static get template() {
    return html`
    <style>
      #app {
        background-color: #f4f4f4;
        font-family: 'Roboto', 'Noto', sans-serif;
      }
      app-header {
        --app-header-shadow: {
          box-shadow: inset 0px 5px 2px -3px rgba(0, 0, 0, 0.9);
        };
        background-color: #4285f4;
        color: white;
      }
      .content {
        padding: 30px;
      }
      last-updated-message {
        padding-right: 1em;
      }
      .subtext {
        font-size: .80em;
      }
      .table {
        padding: 20px 0px;
      }
    </style>
    <link rel="stylesheet" type="text/css" href="/static/icons.css">
    <iron-ajax
      id="ajax"
      url="/prpc/dashboard.ChopsServiceStatus/GetAllServicesData"
      method="POST"
      content-type="application/json"
      accept="json"
      json-prefix=")]}'"
      on-response="_refreshCountdown"
      handle-as="json"
      last-response="{{ajaxResponse}}"
      ></iron-ajax>
    <div id="app">
      <app-header reveals effects="waterfall">
        <app-toolbar>
          <div main-title>Chrome Operations Status Dashboard</div>
          <last-updated-message last-updated="[[lastUpdated]]"></last-updated-message>
          <chops-login
                   login-url="[[loginUrl]]"
                   logout-url="[[logoutUrl]]"
                   user="[[user]]"></chops-login>
        </app-toolbar>
      </app-header>
      <div class="content">
        <tree-status></tree-status>
        <!-- TODO(jojwang): Only the second table is showing up because none of our services have SLAs.
          When there are both tables become visible on the dashboard make it clear to users
          that one table is for services covered by an SLA and one is not.-->
        <template is="dom-if" if="[[services.length]]">
          <div class="table">
            <status-table services="[[services]]" latest-date-ts="{{latestDateTs}}" is-googler="[[isGoogler]]">
            </status-table>
          </div>
        </template>
        <template is="dom-if" if="[[nonSLAServices.length]]">
          <div class="table">
            <status-table services="[[nonSLAServices]]" latest-date-ts="{{latestDateTs}}" is-googler="[[isGoogler]]">
            </status-table>
          </div>
        </template>
        <p class="subtext">
          <i class="green circle"></i> No issues<br/>
          <i class="yellow circle"></i> Slow or experiencing disruptions<br/>
          <i class="red circle"></i> Service outage<br/>
          <p class="subtext">
            Click
            <a href="https://chromium.googlesource.com/infra/infra/+/master/doc/status_dash_def.md">
              here
            </a>
            for more detailed status definitions.
          </p>
        </p>
        <p class="subtext">
          All dates shown are using the local timezone unless otherwise specified.
        </p>
      </div>
    `;
  }
  static get is() { return 'chopsdash-app'; }

  ready() {
    super.ready();
    this._refreshData();
  }

  static get properties() {
    return {
      isGoogler: {
        type: Boolean,
        value: false,
      },
      lastUpdated: {
        type: Object,
        value: {time: moment(Date.now()).format('M/DD/YYYY, h:mm a'), relativeTime: 0}
      },
      // latestDateTs is a timestamp in milliseconds.
      latestDateTs: {
        type: Number,
        notify: true,
        value: new Date().setHours(23, 50, 50, 0),
        observer: '_refreshData',
      },
      loginUrl: {
        type: String,
      },
      logoutUrl: {
        type: String,
      },
      // Services that are not covered by an SLA.
      nonSLAServices: {
        type: Array,
        computed: '_updateNonSLAServices(ajaxResponse)'
      },
      // Services covered by an SLA.
      services: {
        type: Array,
        computed: '_updateServices(ajaxResponse)'
      },
      user: {
        type: String,
      }
    }
  }

  _refreshData() {
    let body = {uptoTime: Math.floor(this.latestDateTs / 1000)};
    this.$.ajax.body = JSON.stringify(body);
    this.$.ajax.generateRequest();
  }

  _refreshCountdown() {
    this._countdown(0);
  }

  _countdown(lastRefresh) {
    const reload_time_min = 5;
    const update_message_time = 60 * 1000;
    if (lastRefresh == reload_time_min) {
      this.set('lastUpdated.relativeTime', 0);
      this.set('lastUpdated.time', moment(Date.now()).format('M/DD/YYYY, h:mm a'));
      this._refreshData();
    } else {
      timeOut.run(() => {
        this.set('lastUpdated.relativeTime', lastRefresh + 1);
        this._countdown(lastRefresh + 1); }, update_message_time);
    }
  }

  _updateServices(jsonData) {
    return jsonData.services;
  }

  _updateNonSLAServices(jsonData) {
    return jsonData.nonslaServices;
  }
}
customElements.define(ChopsdashApp.is, ChopsdashApp);