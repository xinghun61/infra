// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {dom} from '@polymer/polymer/lib/legacy/polymer.dom.js';

import '../../chops/chops-button/chops-button.js';
import '@vaadin/vaadin-upload/vaadin-upload.js';
import '@vaadin/vaadin-upload/theme/lumo/vaadin-upload.js';
import '../../chops/chops-checkbox/chops-checkbox.js';
import '../../mr-error/mr-error.js';
import '../shared/mr-flt-styles.js';
import {MetadataMixin} from '../shared/metadata-mixin.js';
import {selectors} from '../../redux/selectors.js';
import {actionType} from '../../redux/redux-mixin.js';
import './mr-edit-field.js';
import './mr-edit-status.js';


/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
export class MrEditMetadata extends MetadataMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <dom-module id="upload-theme" theme-for="vaadin-upload-file">
        <!-- Custom styling to hide some unused controls and add some
             extra affordances. -->
        <template>
          <style>
            [part="start-button"], [part="status"], [part="progress"] {
              display:none;
            }
            [part="row"]:hover {
              background: #eee;
            }
            [part="clear-button"] {
              cursor: pointer;
              font-size: 100%;
            }
            [part="clear-button"]:before {
              font-family: sans-serif;
              content: 'X';
            }
          </style>
        </template>
      </dom-module>
      <style include="mr-flt-styles">
        :host {
          display: block;
          font-size: 12px;
          --mr-edit-field-styles: {
            box-sizing: border-box;
            width: 95%;
            padding: 0.25em 4px;
          }
        }
        vaadin-upload {
          margin-bottom: 1em;
        }
        input {
          @apply --mr-edit-field-styles;
        }
        label {
          font-weight: bold;
          word-wrap: break-word;
          text-align: right;
        }
        label.checkbox {
          text-align: left;
        }
        textarea {
          width: 100%;
          margin: 0.5em 0;
          box-sizing: border-box;
          border: var(--chops-accessible-border);
          height: 8em;
          transition: height 0.1s ease-in-out;
          padding: 0.5em 4px;
          grid-column-start: 1;
          grid-column-end: 2;
        }
        button.toggle {
          background: none;
          color: var(--chops-link-color);
          border: 0;
          width: 100%;
          padding: 0.25em 0;
          text-align: left;
        }
        button.toggle:hover {
          cursor: pointer;
          text-decoration: underline;
        }
        .discard-button {
          margin-right: 16px;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
        .input-grid {
          padding: 0.5em 0;
          display: grid;
          max-width: 100%;
          grid-gap: 10px;
          grid-template-columns: 120px auto;
          align-items: flex-start;
        }
        .group {
          width: 100%;
          border: 1px solid hsl(0, 0%, 83%);
          grid-column: 1 / -1;
          margin: 0;
          margin-bottom: 0.5em;
          padding: 0;
          padding-bottom: 0.5em;
        }
        .group legend {
          margin-left: 130px;
        }
        .group-title {
          text-align: center;
          font-style: oblique;
          margin-top: 4px;
          margin-bottom: -8px;
        }
        @media (max-width: 600px) {
          label {
            margin-top: 8px;
            text-align: left;
          }
          .input-grid {
            grid-gap: 4px;
            grid-template-columns: 100%;
          }
        }
      </style>
      <template is="dom-if" if="[[error]]">
        <mr-error>[[error]]</mr-error>
      </template>
      <form id="editForm">
        <textarea id="commentText" placeholder="Add a comment"></textarea>
        <vaadin-upload files="{{_newAttachments}}" no-auto hidden$="[[disableAttachments]]">
          <i class="material-icons" slot="drop-label-icon">cloud_upload</i>
        </vaadin-upload>
        <div class="input-grid">
          <template is="dom-if" if="[[!isApproval]]">
            <label for="summaryInput">Summary:</label>
            <input id="summaryInput" value$="[[summary]]" />
          </template>
          <template is="dom-if" if="[[statuses.length]]">
            <label for="statusInput">Status:</label>

            <mr-edit-status
              id="statusInput"
              status="[[status]]"
              statuses="[[statuses]]"
              is-approval="[[isApproval]]"
              merged-into="[[_mapIssueRefToIssueString(mergedInto, projectName)]]"
            ></mr-edit-status>
          </template>


          <template is="dom-if" if="[[!isApproval]]">
            <label for="ownerInput" on-click="_clickLabelForCustomInput">Owner:</label>
            <mr-edit-field
              id="ownerInput"
              type="USER_TYPE"
              initial-values="[[_wrapList(ownerName)]]"
            ></mr-edit-field>

            <label for="ccInput" on-click="_clickLabelForCustomInput">CC:</label>
            <mr-edit-field
              id="ccInput"
              name="cc"
              type="USER_TYPE"
              initial-values="[[_ccNames]]"
              derived-values="[[_derivedCCs]]"
              multi
            ></mr-edit-field>

            <label for="componentsInput" on-click="_clickLabelForCustomInput">Components:</label>
            <mr-edit-field
              id="componentsInput"
              name="component"
              type="STR_TYPE"
              initial-values="[[_mapComponentRefsToNames(components)]]"
              ac-type="component"
              multi
            ></mr-edit-field>
          </template>

          <template is="dom-if" if="[[_and(hasApproverPrivileges, isApproval)]]">
            <label for="approversInput" on-click="_clickLabelForCustomInput">Approvers:</label>
            <mr-edit-field
              id="approversInput"
              type="USER_TYPE"
              initial-values="[[_mapUserRefsToNames(approvers)]]"
              name="approver"
              multi
            ></mr-edit-field>
          </template>

          <template is="dom-repeat" items="[[_fieldDefsWithGroups]]" as="group">
            <fieldset class="group">
              <legend>[[group.groupName]]</legend>
              <div class="input-grid">
                <template is="dom-repeat" items="[[group.fieldDefs]]" as="field">
                  <label
                    hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
                    for$="[[_idForField(field.fieldRef.fieldName)]]"
                    on-click="_clickLabelForCustomInput"
                    title$="[[field.docstring]]"
                  >
                    [[field.fieldRef.fieldName]]:
                  </label>
                  <mr-edit-field
                    hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
                    id$="[[_idForField(field.fieldRef.fieldName)]]"
                    name="[[field.fieldRef.fieldName]]"
                    type="[[field.fieldRef.type]]"
                    options="[[_optionsForField(projectConfig.labelDefs, field.fieldRef.fieldName)]]"
                    initial-values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
                    multi="[[field.isMultivalued]]"
                  ></mr-edit-field>
                </template>
              </div>
            </fieldset>
          </template>

          <template is="dom-repeat" items="[[_fieldDefsWithoutGroup]]" as="field">
            <label
              hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
              for$="[[_idForField(field.fieldRef.fieldName)]]"
              on-click="_clickLabelForCustomInput"
              title$="[[field.docstring]]"
            >
              [[field.fieldRef.fieldName]]:
            </label>
            <mr-edit-field
              hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
              id$="[[_idForField(field.fieldRef.fieldName)]]"
              name="[[field.fieldRef.fieldName]]"
              type="[[field.fieldRef.type]]"
              options="[[_optionsForField(projectConfig.labelDefs, field.fieldRef.fieldName)]]"
              initial-values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
              multi="[[field.isMultivalued]]"
            ></mr-edit-field>
          </template>

          <template is="dom-if" if="[[!isApproval]]">
            <label for="blockedOnInput" on-click="_clickLabelForCustomInput">Blocked on:</label>
            <mr-edit-field
              id="blockedOnInput"
              initial-values="[[_mapBlockerRefsToIdStrings(blockedOn, projectName)]]"
              name="blocked-on"
              multi
            ></mr-edit-field>

            <label for="blockingInput" on-click="_clickLabelForCustomInput">Blocking:</label>
            <mr-edit-field
              id="blockingInput"
              initial-values="[[_mapBlockerRefsToIdStrings(blocking, projectName)]]"
              name="blocking"
              multi
            ></mr-edit-field>

            <label for="labelsInput" on-click="_clickLabelForCustomInput">Labels:</label>
            <mr-edit-field
              id="labelsInput"
              ac-type="label"
              initial-values="[[labelNames]]"
              derived-values="[[derivedLabels]]"
              name="label"
              multi
            ></mr-edit-field>
          </template>

          <span hidden$="[[!_nicheFieldCount]]"></span>
          <button type="button" class="toggle" on-click="toggleNicheFields" hidden$="[[!_nicheFieldCount]]">
            <span hidden$="[[showNicheFields]]">
              Show all fields ([[_nicheFieldCount]] currently hidden)
            </span>
            <span hidden$="[[!showNicheFields]]">
              Hide niche fields ([[_nicheFieldCount]] currently shown)
            </span>
          </button>

          <span></span>
          <chops-checkbox
            id="sendEmail"
            on-checked-change="_sendEmailChecked"
            checked="[[sendEmail]]"
          >Send email</chops-checkbox>
        </div>
        <div class="edit-actions">
          <chops-button
            on-click="discard"
            class="de-emphasized discard-button"
            disabled="[[disabled]]"
          >
            <i class="material-icons">close</i>
            Discard changes
          </chops-button>
          <chops-button on-click="save" class="emphasized" disabled="[[disabled]]">
            <i class="material-icons">create</i>
            Save changes
          </chops-button>
        </div>
      </form>
    `;
  }

  static get is() {
    return 'mr-edit-metadata';
  }

  static get properties() {
    return {
      fieldValueMap: Object,
      approvers: {
        type: Array,
        value: () => [],
      },
      setter: {
        type: Object,
        value: () => {},
      },
      summary: {
        type: String,
        value: '',
      },
      cc: {
        type: Array,
        value: () => [],
      },
      components: {
        type: Array,
        value: () => [],
      },
      status: String,
      statuses: {
        type: Array,
        value: () => [],
      },
      blockedOn: {
        type: Array,
        value: () => [],
      },
      blocking: {
        type: Array,
        value: () => [],
      },
      mergedInto: Object,
      ownerName: {
        type: String,
        value: '',
      },
      labelNames: {
        type: Array,
        value: () => [],
      },
      derivedLabels: {
        type: Array,
        value: [],
      },
      phaseName: String,
      projectConfig: Object,
      projectName: String,
      isApproval: {
        type: Boolean,
        value: false,
      },
      hasApproverPrivileges: {
        type: Boolean,
        value: false,
      },
      showNicheFields: {
        type: Boolean,
        value: false,
      },
      disabled: {
        type: Boolean,
        value: false,
      },
      disableAttachments: {
        type: Boolean,
        value: false,
      },
      error: String,
      sendEmail: {
        type: Boolean,
        value: true,
      },
      _newAttachments: Array,
      _nicheFieldCount: {
        type: Boolean,
        computed: '_computeNicheFieldCount(fieldDefs)',
      },
      _ccNames: {
        type: Array,
        computed: '_computeCCNames(cc)',
      },
      _derivedCCs: {
        type: Array,
        computed: '_computeDerivedCCs(cc)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      projectConfig: state.projectConfig,
      projectName: state.projectName,
      fieldValueMap: selectors.issueFieldValueMap(state),
    };
  }

  connectedCallback() {
    super.connectedCallback();
    this.dispatchAction({type: actionType.UPDATE_FORMS_TO_CHECK, form: this});
  }

  reset() {
    this.$.editForm.reset();

    // Since custom elements containing <input> elements have the inputs
    // wrapped in ShadowDOM, those inputs don't get reset with the rest of
    // the form. Haven't been able to figure out a way to replicate form reset
    // behavior with custom input elements.
    if (this.isApproval) {
      if (this.hasApproverPrivileges) {
        const approversInput = dom(this.root).querySelector(
          '#approversInput');
        if (approversInput) {
          approversInput.reset();
        }
      }
    }
    dom(this.root).querySelectorAll('mr-edit-field').forEach((el) => {
      el.reset();
    });
  }

  save() {
    this.dispatchEvent(new CustomEvent('save'));
  }

  discard() {
    const isDirty = Object.keys(this.getDelta()).length !== 0;
    if (!isDirty || confirm('Discard your changes?')) {
      this.dispatchEvent(new CustomEvent('discard'));
    }
  }

  loadAttachments() {
    if (!this._newAttachments || !this._newAttachments.length) return [];
    return this._newAttachments.map((f) => {
      return this._loadLocalFile(f);
    });
  }

  _loadLocalFile(f) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onloadend = () => {
        resolve({filename: f.name, content: btoa(r.result)});
      };
      r.onerror = () => {
        reject(r.error);
      };

      r.readAsBinaryString(f);
    });
  }

  getDelta() {
    const result = {};
    const root = dom(this.root);

    const statusInput = root.querySelector('#statusInput');
    if (statusInput) {
      Object.assign(result, statusInput.getDelta());
    }

    const commentContent = root.querySelector('#commentText').value;
    if (commentContent) {
      result['comment'] = commentContent;
    }

    if (this.isApproval) {
      if (this.hasApproverPrivileges) {
        const approversInput = root.querySelector('#approversInput');
        const approversAdded = approversInput.getValuesAdded();
        if (approversAdded && approversAdded.length) {
          result['approversAdded'] = approversAdded;
        }
        const approversRemoved = approversInput.getValuesRemoved();
        if (approversRemoved && approversRemoved.length) {
          result['approversRemoved'] = approversRemoved;
        }
      }
    } else {
      // TODO(zhangtiff): Consider representing baked-in fields such as owner,
      // cc, and status similarly to custom fields to reduce repeated code.

      const summaryInput = root.querySelector('#summaryInput');
      if (summaryInput) {
        const newSummary = summaryInput.value;
        if (newSummary !== this.summary) {
          result['summary'] = newSummary;
        }
      }

      const ownerInput = root.querySelector('#ownerInput');
      if (ownerInput) {
        const newOwner = ownerInput.getValue();
        if (newOwner !== this.ownerName) {
          result['owner'] = newOwner;
        }
      }

      this._addListChangesToDelta(result, 'labelsInput',
        'labelsAdded', 'labelsRemoved');

      this._addListChangesToDelta(result, 'ccInput',
        'ccAdded', 'ccRemoved');

      this._addListChangesToDelta(result, 'componentsInput',
        'componentsAdded', 'componentsRemoved');

      this._addListChangesToDelta(result, 'blockedOnInput',
        'blockedOnAdded', 'blockedOnRemoved');

      this._addListChangesToDelta(result, 'blockingInput',
        'blockingAdded', 'blockingRemoved');
    }

    let fieldValuesAdded = [];
    let fieldValuesRemoved = [];

    const fieldDefs = this.fieldDefs || [];
    fieldDefs.forEach((field) => {
      const fieldName = field.fieldRef.fieldName;
      const input = root.querySelector(
        `#${this._idForField(fieldName)}`);
      const valuesAdded = input.getValuesAdded();
      const valuesRemoved = input.getValuesRemoved();

      valuesAdded.forEach((v) => {
        fieldValuesAdded.push({
          fieldRef: {
            fieldName: field.fieldRef.fieldName,
            fieldId: field.fieldRef.fieldId,
          },
          value: v,
        });
      });

      valuesRemoved.forEach((v) => {
        fieldValuesRemoved.push({
          fieldRef: {
            fieldName: field.fieldRef.fieldName,
            fieldId: field.fieldRef.fieldId,
          },
          value: v,
        });
      });
    });

    if (fieldValuesAdded.length) {
      result['fieldValuesAdded'] = fieldValuesAdded;
    }
    if (fieldValuesRemoved.length) {
      result['fieldValuesRemoved'] = fieldValuesRemoved;
    }

    return result;
  }

  toggleNicheFields() {
    this.showNicheFields = !this.showNicheFields;
  }

  _addListChangesToDelta(delta, inputId, addedKey, removedKey) {
    const root = dom(this.root);
    const input = root.querySelector(`#${inputId}`);
    if (!input) return;
    const valuesAdded = input.getValuesAdded();
    const valuesRemoved = input.getValuesRemoved();
    if (valuesAdded && valuesAdded.length) {
      delta[addedKey] = valuesAdded;
    }
    if (valuesRemoved && valuesRemoved.length) {
      delta[removedKey] = valuesRemoved;
    }
  }

  _computeNicheFieldCount(fieldDefs) {
    return fieldDefs.reduce((acc, fd) => acc + (fd.isNiche | 0), 0);
  }

  _mapIssueRefToIssueString(ref, projectName) {
    if (!ref) return '';
    if (ref.projectName === projectName) {
      return `${ref.localId}`;
    }
    return `${ref.projectName}:${ref.localId}`;
  }

  _mapBlockerRefsToIdStrings(arr, projectName) {
    if (!arr || !arr.length) return [];
    return arr.map((v) => this._mapIssueRefToIssueString(v, projectName));
  }

  // For simulating && in templating.
  _and(a, b) {
    return a && b;
  }

  // This function exists because <label for="inputId"> doesn't work for custom
  // input elements.
  _clickLabelForCustomInput(e) {
    const target = e.target;
    const forValue = target.getAttribute('for');
    if (forValue) {
      const customInput = dom(this.root).querySelector('#' + forValue);
      if (customInput && customInput.focus) {
        customInput.focus();
      }
    }
  }

  _idForField(name) {
    return `${name}Input`;
  }

  _computeCCNames(users) {
    if (!users) return [];
    return this._mapUserRefsToNames(users.filter((u) => !u.isDerived));
  }

  _computeDerivedCCs(users) {
    if (!users) return [];
    return this._mapUserRefsToNames(users.filter((u) => u.isDerived));
  }

  _mapUserRefsToNames(users) {
    if (!users) return [];
    return users.map((u) => (u.displayName));
  }

  _mapComponentRefsToNames(components) {
    if (!components) return [];
    return components.map((c) => c.path);
  }

  _optionsForField(labelDefs, fieldName) {
    const options = [];
    labelDefs = labelDefs || [];

    // TODO(zhangtiff): Find a way to avoid traversing through every label on
    // every enum field.
    for (const label of labelDefs) {
      const labelName = label.label;
      if (labelName.toLowerCase().startsWith(fieldName.toLowerCase())) {
        const opt = Object.assign({}, label, {
          optionName: labelName.substring(fieldName.length + 1),
        });
        options.push(opt);
      }
    }
    return options;
  }

  _fieldIsHidden(showNicheFields, isNiche) {
    return !showNicheFields && isNiche;
  }

  _wrapList(item) {
    if (!item) return [];
    return [item];
  }

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
