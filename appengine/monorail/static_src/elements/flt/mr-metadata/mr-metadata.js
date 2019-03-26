// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-timestamp/chops-timestamp.js';
import '../../links/mr-issue-link/mr-issue-link.js';
import '../../links/mr-user-link/mr-user-link.js';
import {MetadataMixin} from '../shared/metadata-mixin.js';
import '../../shared/mr-shared-styles.js';
import './mr-field-values.js';

/**
 * `<mr-metadata>`
 *
 * Generalized metadata for either approvals or issues.
 *
 */
export class MrMetadata extends MetadataMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style include="mr-shared-styles">
        :host {
          display: table;
          table-layout: fixed;
          width: 100%;
        }
        td, th {
          padding: 0.5em 4px;
          vertical-align: top;
          text-overflow: ellipsis;
          overflow: hidden;
        }
        td {
          width: 60%;
        }
        th {
          text-align: left;
          width: 40%;
        }
        .group-separator {
          border-top: var(--chops-normal-border);
        }
        .group-title {
          font-weight: normal;
          font-style: oblique;
          border-bottom: var(--chops-normal-border);
          text-align: center;
        }
      </style>
      <template is="dom-if" if="[[approvalStatus]]">
        <tr>
          <th>Status:</th>
          <td>
            [[approvalStatus]]
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[approvers.length]]">
        <tr>
          <th>Approvers:</th>
          <td>
            <template is="dom-repeat" items="[[approvers]]">
              <mr-user-link
                display-name="[[item.displayName]]"
                user-id="[[item.userId]]"
              ></mr-user-link><br />
            </template>
          </td>
        </tr>
      </template>
      <template is="dom-if" if="[[setter]]">
        <th>Setter:</th>
        <td>
          <mr-user-link
            display-name="[[setter.displayName]]"
            user-id="[[setter.userId]]"
          ></mr-user-link>
        </td>
      </template>

      <template is="dom-if" if="[[owner]]">
        <tr>
          <th>Owner:</th>
          <td>
            <mr-user-link
              display-name="[[owner.displayName]]"
              user-id="[[owner.userId]]"
            ></mr-user-link>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[cc.length]]">
        <tr>
          <th>CC:</th>
          <td>
            <template is="dom-repeat" items="[[cc]]">
              <mr-user-link
                display-name="[[item.displayName]]"
                user-id="[[item.userId]]"
              ></mr-user-link><br />
            </template>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[issueStatus]]">
        <tr>
          <th>Status:</th>
          <td>
            [[issueStatus.status]]
            <em hidden$="[[!issueStatus.meansOpen]]">
              (Open)
            </em>
            <em hidden$="[[issueStatus.meansOpen]]">
              (Closed)
            </em>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[_issueIsDuplicate(issueStatus)]]">
        <tr>
          <th>MergedInto:</th>
          <td>
            <mr-issue-link
              project-name="[[projectName]]"
              issue="[[mergedInto]]"
            ></mr-issue-link>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[components.length]]">
        <tr>
          <th>Components:</th>
          <td>
            <template is="dom-repeat" items="[[components]]">
              <a href$="/p/[[projectName]]/issues/list?q=component:[[item.path]]"
                title$="[[item.path]] = [[item.docstring]]"
              >
                [[item.path]]</a><br />
            </template>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[modifiedTimestamp]]">
        <tr>
          <th>Modified:</th>
          <td>
            <chops-timestamp timestamp="[[modifiedTimestamp]]" short></chops-timestamp>
          </td>
        </tr>
      </template>

      <template is="dom-repeat" items="[[_fieldDefsWithGroups]]" as="group">
        <tr>
          <th class="group-title" colspan="2">
            [[group.groupName]]
          </th>
        </tr>
        <template is="dom-repeat" items="[[group.fieldDefs]]" as="field">
          <tr hidden$="[[_fieldIsHidden(fieldValueMap, field)]]">
            <th title$="[[field.docstring]]">[[field.fieldRef.fieldName]]:</th>
            <td>
              <mr-field-values
                name="[[field.fieldRef.fieldName]]"
                type="[[field.fieldRef.type]]"
                values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
                project-name="[[projectName]]"
              ></mr-field-values>
            </td>
          </tr>
        </template>
        <tr>
          <th class="group-separator" colspan="2"></th>
        </tr>
      </template>

      <template is="dom-repeat" items="[[_fieldDefsWithoutGroup]]" as="field">
        <tr hidden$="[[_fieldIsHidden(fieldValueMap, field)]]">
          <th title$="[[field.fieldRef.fieldName]]">[[field.fieldRef.fieldName]]:</th>
          <td>
            <mr-field-values
              name="[[field.fieldRef.fieldName]]"
              type="[[field.fieldRef.type]]"
              values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName)]]"
              project-name="[[projectName]]"
            ></mr-field-values>
          </td>
        </tr>
      </template>
    `;
  }

  static get is() {
    return 'mr-metadata';
  }

  static get properties() {
    return {
      approvalStatus: String,
      approvers: Array,
      setter: Object,
      cc: Array,
      components: Array,
      issueStatus: String,
      mergedInto: Object,
      owner: Object,
      isApproval: {
        type: Boolean,
        value: false,
      },
      projectName: String,
      issueId: Number,
      role: {
        type: String,
        value: 'table',
        reflectToAttribute: true,
      },
      fieldValueMap: Object, // Set by MetadataMixin.
    };
  }

  static mapStateToProps(state, element) {
    const superProps = super.mapStateToProps(state, element);
    return Object.assign(superProps, {
      projectName: state.projectName,
      issueId: state.issueId,
      relatedIssues: state.relatedIssues,
    });
  }

  _fieldIsHidden(fieldValueMap, fieldDef) {
    return fieldDef.isNiche && !this._valuesForField(fieldValueMap,
      fieldDef.fieldRef.fieldName).length;
  }

  _issueIsDuplicate(issueStatus) {
    return issueStatus.status === 'Duplicate';
  }
}

customElements.define(MrMetadata.is, MrMetadata);
