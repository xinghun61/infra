// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import page from 'page';
import qs from 'qs';
import {ChopsChoiceButtons} from
  'elements/chops/chops-choice-buttons/chops-choice-buttons.js';

export class MrModeSelector extends ChopsChoiceButtons {
  static get properties() {
    return {
      ...ChopsChoiceButtons.properties,
      queryParams: {type: Object},
      projectName: {type: String},
    };
  }
  constructor() {
    super();
    this.options = [
      {text: 'List', value: 'list'},
      {text: 'Grid', value: 'grid'},
      {text: 'Chart', value: 'chart'},
    ];

    this.queryParams = {};
    this.projectName = '';

    this._page = page;
  };

  connectedCallback() {
    super.connectedCallback();

    this.addEventListener('change', (e) => this._selectMode(e));
  }

  _selectMode(e) {
    const value = e.target.value.toLowerCase();

    const newParams = {...this.queryParams};

    if (value.toLowerCase() === 'list') {
      delete newParams.mode;
    } else {
      newParams.mode = value;
    }

    const params = qs.stringify(newParams);
    const newURL =
        `/p/${this.projectName}/issues/list${params ? '?' : ''}${params}`;
    this._page(newURL);
  }
};

customElements.define('mr-mode-selector', MrModeSelector);
