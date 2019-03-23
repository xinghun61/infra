// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {Debouncer} from '@polymer/polymer/lib/utils/debounce.js';
import {timeOut} from '@polymer/polymer/lib/utils/async.js';

import '../../chops/chops-button/chops-button.js';
import '@vaadin/vaadin-upload/vaadin-upload.js';
import '@vaadin/vaadin-upload/theme/lumo/vaadin-upload.js';
import '../../chops/chops-checkbox/chops-checkbox.js';
import '../../mr-error/mr-error.js';
import '../../mr-warning/mr-warning.js';
import {displayNameToUserRef, labelStringToRef, componentStringToRef,
  issueStringToRef, issueRefToString} from '../../shared/converters.js';
import {isEmptyObject} from '../../shared/helpers.js';
import '../../shared/mr-shared-styles.js';
import {MetadataMixin} from '../shared/metadata-mixin.js';
import * as project from '../../redux/project.js';
import {selectors} from '../../redux/selectors.js';
import {actionType} from '../../redux/redux-mixin.js';
import './mr-edit-field.js';
import './mr-edit-status.js';
import {ISSUE_EDIT_PERMISSION} from '../../shared/permissions.js';


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
      <style include="mr-shared-styles">
        :host {
          display: block;
          font-size: 12px;
          --mr-edit-field-styles: {
            box-sizing: border-box;
            width: 95%;
            padding: 0.25em 4px;
          }
        }
        :host(.edit-actions-right) .edit-actions {
          flex-direction: row-reverse;
          text-align: right;
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
        .presubmit-derived {
          color: gray;
          font-style: italic;
          text-decoration-line: underline;
          text-decoration-style: dotted;
        }
        .presubmit-derived-header {
          color: gray;
          font-weight: bold;
        }
        .discard-button {
          margin-right: 16px;
          margin-left: 16px;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: left;
          display: flex;
          flex-direction: row;
          justify-content: flex-start;
        }
        .edit-actions chops-button {
          flex-grow: 0;
          flex-shrink: 0;
        }
        .edit-actions .emphasized {
          margin-left: 0;
        }
        .input-grid {
          padding: 0.5em 0;
          display: grid;
          max-width: 100%;
          grid-gap: 8px;
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
            grid-gap: 8px;
            grid-template-columns: 100%;
          }
        }
      </style>
      <template is="dom-if" if="[[error]]">
        <mr-error>[[error]]</mr-error>
      </template>
      <form id="editForm">
        <textarea
          id="commentText"
          placeholder="Add a comment"
          on-keyup="_onChange"
        ></textarea>
        <vaadin-upload
          files="{{newAttachments}}"
          no-auto
          hidden$="[[disableAttachments]]"
        >
          <i class="material-icons" slot="drop-label-icon">cloud_upload</i>
        </vaadin-upload>
        <div class="input-grid">
          <template is="dom-if" if="[[_canEditIssue]]">
            <template is="dom-if" if="[[!isApproval]]">
              <label for="summaryInput">Summary:</label>
              <input
                id="summaryInput"
                value$="[[summary]]"
                on-keyup="_onChange"
              />
            </template>
            <template is="dom-if" if="[[statuses.length]]">
              <label for="statusInput">Status:</label>

              <mr-edit-status
                id="statusInput"
                status="[[status]]"
                statuses="[[statuses]]"
                is-approval="[[isApproval]]"
                merged-into="[[_computeMergedIntoString(projectName, mergedInto)]]"
                on-change="_onChange"
              ></mr-edit-status>
            </template>


            <template is="dom-if" if="[[!isApproval]]">
              <label for="ownerInput" on-click="_clickLabelForCustomInput">Owner:</label>
              <mr-edit-field
                id="ownerInput"
                type="USER_TYPE"
                initial-values="[[_wrapList(ownerName)]]"
                on-change="_onChange"
              ></mr-edit-field>

              <label for="ccInput" on-click="_clickLabelForCustomInput">CC:</label>
              <mr-edit-field
                id="ccInput"
                name="cc"
                type="USER_TYPE"
                initial-values="[[_ccNames]]"
                derived-values="[[_derivedCCs]]"
                on-change="_onChange"
                multi
              ></mr-edit-field>

              <label for="componentsInput" on-click="_clickLabelForCustomInput">Components:</label>
              <mr-edit-field
                id="componentsInput"
                name="component"
                type="STR_TYPE"
                initial-values="[[_mapComponentRefsToNames(components)]]"
                ac-type="component"
                on-change="_onChange"
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
                on-change="_onChange"
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
                      on-change="_onChange"
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
                on-change="_onChange"
              ></mr-edit-field>
            </template>

            <template is="dom-if" if="[[!isApproval]]">
              <label for="blockedOnInput" on-click="_clickLabelForCustomInput">Blocked on:</label>
              <mr-edit-field
                id="blockedOnInput"
                initial-values="[[_mapBlockerRefsToIdStrings(blockedOn, projectName)]]"
                name="blocked-on"
                on-change="_onChange"
                multi
              ></mr-edit-field>

              <label for="blockingInput" on-click="_clickLabelForCustomInput">Blocking:</label>
              <mr-edit-field
                id="blockingInput"
                initial-values="[[_mapBlockerRefsToIdStrings(blocking, projectName)]]"
                name="blocking"
                on-change="_onChange"
                multi
              ></mr-edit-field>

              <label for="labelsInput" on-click="_clickLabelForCustomInput">Labels:</label>
              <mr-edit-field
                id="labelsInput"
                ac-type="label"
                initial-values="[[labelNames]]"
                derived-values="[[derivedLabels]]"
                name="label"
                on-change="_onChange"
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
          </template>

          <template is="dom-if" if="[[_hasErrorsOrWarnings(presubmitResponse)]]">
            <span></span>
            <div id="presubmit-errors-and-warnings">
              <template is="dom-repeat" items="[[presubmitResponse.warnings]]">
                <mr-warning title="[[item.why]]">[[item.value]]</mr-warning>
              </template>
              // TODO(ehmaldonado): Look into blocking submission on presubmit
              // errors.
              <template is="dom-repeat" items="[[presubmitResponse.errors]]">
                <mr-error title="[[item.why]]">[[item.value]]</mr-error>
              </template>
            </div>
          </template>

          <span></span>
          <div class="edit-actions">
            <chops-button on-click="save" class="emphasized" disabled="[[disabled]]">
              Save changes
            </chops-button>
            <chops-button
              on-click="discard"
              class="de-emphasized discard-button"
              disabled="[[disabled]]"
            >
              Discard
            </chops-button>
          </div>

          <template is="dom-if" if="[[_hasDerivedValues(presubmitResponse)]]">
            <span></span>
            <div class="presubmit-derived-header">
              Filter rules and components will add
            </div>
          </template>

          <template is="dom-if" if="[[presubmitResponse.derivedCcs]]">
            <label
              for="derived-ccs"
              class="presubmit-derived-header"
            >CCs:</label>
            <div id="derived-ccs">
              <template
                is="dom-repeat"
                items="[[presubmitResponse.derivedCcs]]"
              >
                <span
                  title="[[item.why]]"
                  class="presubmit-derived"
                >[[item.value]]</span>
              </template>
            </div>
          </template>

          <template is="dom-if" if="[[presubmitResponse.derivedLabels]]">
            <label
              for="derived-labels"
              class="presubmit-derived-header"
            >Labels:</label>
            <div id="derived-labels">
              <template
                is="dom-repeat"
                items="[[presubmitResponse.derivedLabels]]"
              >
                <span
                  title="[[item.why]]"
                  class="presubmit-derived"
                >[[item.value]]</span>
              </template>
            </div>
          </template>
        </div>
      </form>
    `;
  }

  static get is() {
    return 'mr-edit-metadata';
  }

  static get properties() {
    return {
      formName: String,
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
      issuePermissions: Object,
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
      newAttachments: Array,
      presubmitResponse: Object,
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
      _canEditIssue: {
        type: Boolean,
        computed: '_computeCanEditIssue(issuePermissions)',
      },
      _debouncedOnChange: Object,
    };
  }

  static mapStateToProps(state, element) {
    return {
      presubmitResponse: state.presubmitResponse,
      projectConfig: project.project(state).config,
      projectName: state.projectName,
      fieldValueMap: selectors.issueFieldValueMap(state),
      issuePermissions: state.issuePermissions,
    };
  }

  reset() {
    this.shadowRoot.querySelector('#editForm').reset();
    const statusInput = this.shadowRoot.querySelector('#statusInput');
    if (statusInput) {
      statusInput.reset();
    }

    // Since custom elements containing <input> elements have the inputs
    // wrapped in ShadowDOM, those inputs don't get reset with the rest of
    // the form. Haven't been able to figure out a way to replicate form reset
    // behavior with custom input elements.
    if (this.isApproval) {
      if (this.hasApproverPrivileges) {
        const approversInput = this.shadowRoot.querySelector(
          '#approversInput');
        if (approversInput) {
          approversInput.reset();
        }
      }
    }
    this.shadowRoot.querySelectorAll('mr-edit-field').forEach((el) => {
      el.reset();
    });
    this.shadowRoot.querySelector('vaadin-upload').files = [];

    this._onChange();
  }

  save() {
    this.dispatchEvent(new CustomEvent('save'));
  }

  discard() {
    const isDirty = this.getCommentContent() || !isEmptyObject(this.getDelta());
    if (!isDirty || confirm('Discard your changes?')) {
      this.dispatchEvent(new CustomEvent('discard'));
    }
  }

  focus() {
    this.shadowRoot.querySelector('#commentText').focus();
  }

  getCommentContent() {
    return this.shadowRoot.querySelector('#commentText').value;
  }

  getDelta() {
    if (!this._canEditIssue) return {};

    const result = {};
    const root = this.shadowRoot;

    const statusInput = root.querySelector('#statusInput');
    if (statusInput) {
      Object.assign(result, statusInput.getDelta(this.projectName));
    }

    if (this.isApproval) {
      if (this.hasApproverPrivileges) {
        this._addListChangesToDelta(
          result, 'approversInput', 'approverRefsAdd', 'approverRefsRemove',
          displayNameToUserRef);
      }
    } else {
      // TODO(zhangtiff): Consider representing baked-in fields such as owner,
      // cc, and status similarly to custom fields to reduce repeated code.

      const summaryInput = root.querySelector('#summaryInput');
      if (summaryInput) {
        const newSummary = summaryInput.value;
        if (newSummary !== this.summary) {
          result.summary = newSummary;
        }
      }

      const ownerInput = root.querySelector('#ownerInput');
      if (ownerInput) {
        const newOwner = ownerInput.getValue();
        if (newOwner !== this.ownerName) {
          result.ownerRef = displayNameToUserRef(newOwner);
        }
      }

      this._addListChangesToDelta(result, 'labelsInput',
        'labelRefsAdd', 'labelRefsRemove', labelStringToRef);

      this._addListChangesToDelta(result, 'ccInput',
        'ccRefsAdd', 'ccRefsRemove', displayNameToUserRef);

      this._addListChangesToDelta(result, 'componentsInput',
        'compRefsAdd', 'compRefsRemove', componentStringToRef);

      this._addListChangesToDelta(result, 'blockedOnInput',
        'blockedOnRefsAdd', 'blockedOnRefsRemove',
        issueStringToRef.bind(null, this.projectName));

      this._addListChangesToDelta(result, 'blockingInput',
        'blockingRefsAdd', 'blockingRefsRemove',
        issueStringToRef.bind(null, this.projectName));
    }

    const fieldDefs = this.fieldDefs || [];
    fieldDefs.forEach((field) => {
      const fieldNameInput = this._idForField(field.fieldRef.fieldName);
      this._addListChangesToDelta(
        result, fieldNameInput, 'fieldValsAdd', 'fieldValsRemove',
        (v) => {
          return {
            fieldRef: {
              fieldName: field.fieldRef.fieldName,
              fieldId: field.fieldRef.fieldId,
            },
            value: v,
          };
        }
      );
    });

    return result;
  }

  toggleNicheFields() {
    this.showNicheFields = !this.showNicheFields;
  }

  _onChange() {
    this._debouncedOnChange = Debouncer.debounce(
      this._debouncedOnChange,
      timeOut.after(400),
      () => {
        const delta = this.getDelta();
        const commentContent = this.getCommentContent();
        this.dispatchAction({
          type: actionType.REPORT_DIRTY_FORM,
          name: this.formName,
          isDirty: !isEmptyObject(delta) || Boolean(commentContent),
        });
        this.dispatchEvent(new CustomEvent('change', {detail: {delta}}));
      });
  }

  _addListChangesToDelta(delta, inputId, addedKey, removedKey, mapFn) {
    const root = this.shadowRoot;
    const input = root.querySelector(`#${inputId}`);
    if (!input) return;
    const valuesAdded = input.getValuesAdded();
    const valuesRemoved = input.getValuesRemoved();
    if (valuesAdded && valuesAdded.length) {
      delta[addedKey] = valuesAdded.map(mapFn);
    }
    if (valuesRemoved && valuesRemoved.length) {
      delta[removedKey] = valuesRemoved.map(mapFn);
    }
  }

  _computeNicheFieldCount(fieldDefs) {
    return fieldDefs.reduce((acc, fd) => acc + (fd.isNiche | 0), 0);
  }

  _mapBlockerRefsToIdStrings(arr, projectName) {
    if (!arr || !arr.length) return [];
    return arr.map((ref) => issueRefToString(ref, projectName));
  }

  // For simulating && in templating.
  _and(a, b) {
    return a && b;
  }

  _hasDerivedValues(response) {
    return ((response.derivedCcs && response.derivedCcs.length)
      || (response.derivedLabels && response.derivedLabels.length));
  }

  _hasErrorsOrWarnings(response) {
    return ((response.errors && response.errors.length)
      || (response.warnings && response.warnings.length));
  }

  // This function exists because <label for="inputId"> doesn't work for custom
  // input elements.
  _clickLabelForCustomInput(e) {
    const target = e.target;
    const forValue = target.getAttribute('for');
    if (forValue) {
      const customInput = this.shadowRoot.querySelector('#' + forValue);
      if (customInput && customInput.focus) {
        customInput.focus();
      }
    }
  }

  _idForField(name) {
    return `${name}Input`;
  }

  _computeCanEditIssue(issuePermissions) {
    return (issuePermissions || []).includes(ISSUE_EDIT_PERMISSION);
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

  // Needed because Polymer doesn't accept non member functions.
  // TODO(ehmaldonado): Remove
  _computeMergedIntoString(projectName, ref) {
    return [issueRefToString(ref, projectName)];
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
