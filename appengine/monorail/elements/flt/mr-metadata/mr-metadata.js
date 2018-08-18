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
      fieldGroups: {
        type: Array,
        // TODO(zhangtiff): Remove this hardcoded data once backend custom
        // field grouping is implemented.
        value: () => [
          {
            groupName: 'Feature Team',
            fieldNames: ['PM', 'Tech Lead', 'Tech-Lead', 'TechLead', 'TL',
              'Team', 'UX', 'TE'],
          },
          {
            groupName: 'Docs',
            fieldNames: ['PRD', 'DD', 'Design Doc', 'Design-Doc',
              'DesignDoc', 'Mocks', 'Test Plan', 'Test-Plan', 'TestPlan',
              'Metrics'],
          },
        ],
      },
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
        value: () => {},
      },
      _fieldGroupMap: {
        type: Object,
        computed: '_computeFieldGroupMap(fieldGroups)',
        value: () => {},
      },
      _fieldGroupsWithDefs: {
        type: Array,
        computed: '_computeFieldGroupsWithDefs(fieldDefs, fieldGroups)',
      },
      _fieldDefsWithoutGroup: {
        type: Array,
        computed: '_computeFieldDefsWithoutGroup(fieldDefs, _fieldGroupMap)',
      },
    };
  }

  _computeFieldValueMap(fields) {
    return computeFunction.computeFieldValueMap(fields);
  }

  _computeFieldGroupMap(fieldGroups) {
    return fieldGroups.reduce((acc, group) => {
      return group.fieldNames.reduce((acc, fieldName) => {
        acc[fieldName] = group.groupName;
        return acc;
      }, acc);
    }, {});
  }

  _computeFieldGroupsWithDefs(fieldDefs, fieldGroups) {
    if (!fieldDefs) return [];
    return fieldGroups.reduce((acc, group) => {
      const groupFields = group.fieldNames.reduce((acc, name) => {
        const fd = fieldDefs.find((fd) => (fd.fieldRef.fieldName == name));
        if (fd) {
          acc.push(fd);
        }
        return acc;
      }, []);
      if (groupFields.length > 0) {
        acc.push({
          groupName: group.groupName,
          fieldDefs: groupFields,
        });
      }
      return acc;
    }, []);
  }

  _computeFieldDefsWithoutGroup(fieldDefs, fieldGroupMap) {
    if (!fieldDefs) return [];
    return fieldDefs.filter((fd) => {
      return !(fd.fieldRef.fieldName in fieldGroupMap);
    });
  }

  _fieldIsHidden(fieldValueMap, fieldDef) {
    return fieldDef.isNiche && !this._valuesForDef(
      fieldDef.fieldRef.fieldName, fieldValueMap).length;
  }

  _valuesForDef(name, fieldValueMap) {
    if (!(name in fieldValueMap)) return [];
    return fieldValueMap[name];
  }
}

customElements.define(MrMetadata.is, MrMetadata);
