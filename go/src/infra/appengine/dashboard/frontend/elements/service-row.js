// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

import 'incident-icon.js';

/**
 *`<service-row>`
 *
 * A row to hold incidents for one service.
 *
 */
export class ServiceRow extends PolymerElement {
  static get template() {
    return html`
      <span>
        <template is="dom-repeat" items="{{incidents}}">
          <incident-icon incident="[[item]]" dates="[[dates]]" is-googler="[[isGoogler]]"></incident-icon>
        </template>
      </span>
    `;
  }

  static get is() {return 'service-row'; }
  static get properties() {
    return {
      // Array of ChopsIncident objects.
      incidents: {
        type: Array,
        value: () => { return []; },
      },
      // Array of Date objects.
      dates: {
        type: Array,
        value: [],
      },
      isGoogler: {
        type: Boolean,
        value: false,
      }
    }
  }
}
customElements.define(ServiceRow.is, ServiceRow);
