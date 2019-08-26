// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {ChopsAutocomplete} from
  'elements/chops/chops-autocomplete/chops-autocomplete';
import {connectStore} from 'reducers/base.js';
import * as user from 'reducers/user.js';

/**
 * `<mr-autocomplete>` displays a single chip.
 *
 */
export class MrAutocomplete extends connectStore(ChopsAutocomplete) {
  static get properties() {
    return {
      ...ChopsAutocomplete.properties,
      /**
       * String for the name of autocomplete vocabulary used.
       * Valid values: 'project'
       */
      vocabularyName: {type: String},
      /**
       * Object where the keys are 'type' values and each value is an object
       * with the format {strings, docDict, replacer}.
       */
      vocabularies: {type: Object},
    };
  }

  constructor() {
    super();
    this.vocabularyName = '';
    this.vocabularies = {};
  }

  stateChanged(state) {
    const userProjects = user.projects(state);
    const {ownerOf = [], memberOf = [], contributorTo = []} = userProjects;

    const strings = [...ownerOf, ...memberOf, ...contributorTo];
    this.vocabularies = {
      'project': {strings},
    };
  }

  update(changedProperties) {
    if (changedProperties.has('vocabularyName')
        || changedProperties.has('vocabularies')) {
      if (this.vocabularyName in this.vocabularies) {
        const props = this.vocabularies[this.vocabularyName];

        this.strings = props.strings || [];
        this.docDict = props.docDict || {};
        this.replacer = props.replacer;
      } else {
        // Clear autocomplete if there's no data for it.
        this.strings = [];
        this.docDict = {};
        this.replacer = null;
      }
    }

    super.update(changedProperties);
  }
}
customElements.define('mr-autocomplete', MrAutocomplete);
