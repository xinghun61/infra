// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {css} from 'lit-element';
import {ChopsCheckbox} from '@chopsui/chops-checkbox';

export class ChopsSwitch extends ChopsCheckbox {
  static get styles() {
    return css`
      :host {
        padding: 8px;
      }
      input {
        display: none;
      }
      label {
        position: relative;
        cursor: pointer;
        padding: 8px 0 8px 44px;
      }
      label:before, label:after {
        content: "";
        position: absolute;
        margin: 0;
        outline: 0;
        top: 50%;
        transform: translate(0, -50%);
      }
      label:before {
        left: 1px;
        width: 34px;
        height: 14px;
        background-color: var(--chops-switch-off-dark-color, grey);
        border-radius: 8px;
      }
      label:after {
        background-color: var(--chops-switch-off-light-color, lightgrey);
        border-radius: 50%;
        box-shadow: var(--chops-switch-shadow);
        height: 20px;
        left: 0;
        width: 20px;
      }
      input:checked + label:before {
        background-color: var(--chops-switch-on-light-color, lightblue);
      }
      input:checked + label:after {
        background-color: var(--chops-switch-on-dark-color, blue);
        transform: translate(80%, -50%);
      }
    `;
  }
}

customElements.define('chops-switch', ChopsSwitch);
