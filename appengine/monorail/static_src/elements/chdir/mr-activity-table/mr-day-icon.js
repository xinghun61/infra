// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class MrDayIcon extends LitElement {
  static get styles() {
    return css`
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
      :host([activityLevel="0"]) {
        background-color: var(--chops-blue-gray-50);
      }
      :host([activityLevel="1"]) {
        background-color: hsl(87, 70%, 87%);
      }
      :host([activityLevel="2"]) {
        background-color: hsl(88, 67%, 72%);
      }
      :host([activityLevel="3"]) {
        background-color: hsl(87, 80%, 40%);
      }
      :host([selected]) {
        border-color: hsl(0, 0%, 13%);
      }
      .hover-card {
        display: none;
      }
      :host(:hover) .hover-card {
        display: block;
        position: relative;
        width: 150px;
        padding: 0.5em 8px;
        background: rgba(0, 0, 0, 0.6);
        color: white;
        border-radius: 8px;
        top: 120%;
        left: 50%;
        transform: translateX(-50%);
      }
    `;
  }

  render() {
    return html`
      <div class="hover-card">
        ${this.commentCount} Comments<br>
        <chops-timestamp .timestamp=${this.date}></chops-timestamp>
      </div>
    `;
  }

  static get properties() {
    return {
      activityLevel: {
        type: Number,
        reflect: true,
      },
      commentCount: {type: Number},
      date: {type: Number},
      selected: {
        type: Boolean,
        reflect: true,
      },
    };
  }

  update(changedProperties) {
    if (changedProperties.has('commentCount')) {
      const level = Math.ceil(this.commentCount / 2);
      this.activityLevel = Math.min(level, 3);
    }
    super.update(changedProperties);
  }
}
customElements.define('mr-day-icon', MrDayIcon);
