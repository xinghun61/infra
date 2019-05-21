// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import '@polymer/paper-tooltip/paper-tooltip.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

export class MrDayIcon extends PolymerElement {
  static get template() {
    return html`
      <style>
        :host {
          background-color: hsl(0, 0%, 95%);
          margin: 0.25em 8px;
          height: 20px;
          width: 20px;
          border: 2px solid white;
          transition: border-color .5s ease-in-out;
        }
        :host(:hover) {
          cursor: pointer;
          border-color: hsl(87, 20%, 45%);
        }
        :host([activity-level="0"]) {
          background-color: hsl(107, 10%, 97%);
        }
        :host([activity-level="1"]) {
          background-color: hsl(87, 70%, 87%);
        }
        :host([activity-level="2"]) {
          background-color: hsl(88, 67%, 72%);
        }
        :host([activity-level="3"]) {
          background-color: hsl(87, 80%, 40%);
        }
        :host([class="selected"]) {
          border-color: hsl(0, 0%, 13%);
        }
      </style>
      <paper-tooltip>
        [[commits]] Commits<br>
        [[comments]] Comments<br>
        <chops-timestamp timestamp="[[date]]"></chops-timestamp>
      </paper-tooltip>
    `;
  }

  static get is() {
    return 'mr-day-icon';
  }

  static get properties() {
    return {
      activityLevel: {
        type: Number,
        reflectToAttribute: true,
      },
      commits: {
        type: Number,
      },
      comments: {
        type: Number,
      },
      date: {
        type: Number,
      },
      class: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeClass(selected)',
      },
      selected: {
        type: Boolean,
        value: false,
      },
    };
  }

  _computeClass(selected) {
    return selected ? 'selected' : '';
  }
}
customElements.define(MrDayIcon.is, MrDayIcon);
