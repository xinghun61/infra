// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../links/mr-user-link/mr-user-link.js';
import {fieldTypes} from '../../shared/field-types.js';
/**
 * `<mr-field-values>`
 *
 * Takes in a list of field values and a single fieldDef and displays them
 * according to their type.
 *
 */
export class MrFieldValues extends PolymerElement {
  static get template() {
    return html`
      <template is="dom-if" if="[[_fieldIsUrl(type)]]">
        <template is="dom-repeat" items="[[values]]" as="value">
          <a href\$="[[value]]">[[value]]</a>
        </template>
      </template>

      <template is="dom-if" if="[[_fieldIsUser(type)]]">
        <template is="dom-repeat" items="[[values]]" as="value">
          <mr-user-link user-id="[[value]]" display-name="[[value]]"></mr-user-link>
        </template>
      </template>

      <template is="dom-if" if="[[_fieldIsRemainingTypes(type)]]">
        <template is="dom-repeat" items="[[values]]" as="value">
          <a href\$="/p/[[projectName]]/issues/list?q=[[name]]=&quot;[[value]]&quot;">
            [[value]]</a><span hidden\$="[[_isLastItem(values.length, index)]]">,</span>
        </template>
      </template>

      <template is="dom-if" if="[[!values.length]]">
        ----
      </template>
    `;
  }

  static get is() {
    return 'mr-field-values';
  }

  static get properties() {
    return {
      name: String,
      type: Object,
      projectName: String,
      values: {
        type: Array,
        value: () => [],
      },
    };
  }

  _fieldIsDate(type) {
    return type === fieldTypes.DATE_TYPE;
  }

  _fieldIsEnum(type) {
    return type === fieldTypes.ENUM_TYPE;
  }

  _fieldIsInt(type) {
    return type === fieldTypes.INT_TYPE;
  }

  _fieldIsStr(type) {
    return type === fieldTypes.STR_TYPE;
  }

  _fieldIsUser(type) {
    return type === fieldTypes.USER_TYPE;
  }

  _fieldIsUrl(type) {
    return type === fieldTypes.URL_TYPE;
  }

  _fieldIsRemainingTypes(type) {
    return this._fieldIsDate(type) || this._fieldIsEnum(type) ||
      this._fieldIsInt(type) || this._fieldIsStr(type);
  }

  _isLastItem(l, i) {
    return i >= l - 1;
  }
}

customElements.define(MrFieldValues.is, MrFieldValues);
