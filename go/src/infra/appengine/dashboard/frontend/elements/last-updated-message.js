// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

export class LastUpdatedMessage extends PolymerElement {
  static get template() {
    return html`
      <style>
        div {
          font-size: .81em;
        }
        #lastUpdatedTimeShort {
          display: none;
        }
        @media (max-width: 800px) {
          #lastUpdatedTimeShort {
            /* Responsively display a shorter last updated time. */
            display: inline;
          }
          #lastUpdatedTime {
            display: none;
          }
        }
      </style>
      <div id="lastUpdated">
        Last updated:
        <span id="lastUpdatedTime">
          <span class="line">[[lastUpdated.time]]</span>
          <span class="line">
            ([[lastUpdated.relativeTime]] minute[[isPlural(lastUpdated.relativeTime)]] ago)
          </span>
        </span>
        <span id="lastUpdatedTimeShort">
          [[lastUpdated.relativeTime]] minutes ago
        </span>
      </div>
    `;
  }

  static get is() { return 'last-updated-message'; }

  ready() {
    super.ready();
  }

  static get properties() {
    return {
      lastUpdated: {
        type: Object,
        value: null,
      }
    }
  }

  isPlural(amount) {
    return amount !== 1 ? 's' : '';
  }
}
customElements.define(LastUpdatedMessage.is, LastUpdatedMessage);
