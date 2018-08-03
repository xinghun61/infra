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
        value: {},
      },
    };
  }

  _computeFieldValueMap(fields) {
    return computeFunction.computeFieldValueMap(fields);
  }

  _valuesForDef(name, fieldValueMap) {
    if (!(name in fieldValueMap)) return [];
    return fieldValueMap[name];
  }
}

customElements.define(MrMetadata.is, MrMetadata);
