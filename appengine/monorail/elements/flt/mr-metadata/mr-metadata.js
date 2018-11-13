'use strict';

/**
 * `<mr-metadata>`
 *
 * Generalized metadata for either approvals or issues.
 *
 */
class MrMetadata extends MetadataMixin(Polymer.Element) {
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
      blockedOn: Array,
      blocking: Array,
      owner: Object,
      phaseName: String,
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      role: {
        type: String,
        value: 'table',
        reflectToAttribute: true,
        readOnly: true,
      },
    };
  }

  _fieldIsHidden(fieldValueMap, fieldDef) {
    return fieldDef.isNiche && !this._valuesForField(fieldValueMap,
      fieldDef.fieldRef.fieldName).length;
  }
}

customElements.define(MrMetadata.is, MrMetadata);
