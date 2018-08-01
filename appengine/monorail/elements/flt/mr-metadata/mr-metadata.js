'use strict';

/**
 * `<mr-metadata>`
 *
 * Generalized metadata for either approvals or issues.
 *
 */
class MrMetadata extends ReduxMixin(Polymer.Element) {
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
      fieldDefs: Array,
      fieldValues: Array,
      issueStatus: String,
      blockedOn: Array,
      blocking: Array,
      owner: Object,
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      _fieldValueMap: {
        type: Object,
        computed: '_computeFieldValueMap(fieldValues)',
      },
    };
  }

  _computeFieldValueMap(fields) {
    return computeFunction.computeFieldValueMap(fields);
  }

  _valuesForDef(fieldDef, fieldValueMap) {
    if (!(fieldDef.fieldRef.fieldName in fieldValueMap)) return [];
    return fieldValueMap[fieldDef.fieldRef.fieldName];
  }
}

customElements.define(MrMetadata.is, MrMetadata);
