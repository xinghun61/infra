// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';

// TODO(zhangtiff): Remove this hardcoded data once backend custom
// field grouping is implemented.
export const HARDCODED_FIELD_GROUPS = [
  {
    groupName: 'Feature Team',
    fieldNames: ['PM', 'Tech Lead', 'Tech-Lead', 'TechLead', 'TL',
      'Team', 'UX', 'TE'],
    applicableType: 'FLT-Launch',
  },
  {
    groupName: 'Docs',
    fieldNames: ['PRD', 'DD', 'Design Doc', 'Design-Doc',
      'DesignDoc', 'Mocks', 'Test Plan', 'Test-Plan', 'TestPlan',
      'Metrics'],
    applicableType: 'FLT-Launch',
  },
];

export const MetadataMixin = (superClass) => {
  return class extends ReduxMixin(superClass) {
    static get properties() {
      return {
        issueType: String,
        fieldDefs: Array,
        fieldValueMap: Object,
        fieldGroups: {
          type: Array,
          value: () => HARDCODED_FIELD_GROUPS,
        },
        _filteredGroups: {
          type: Array,
          computed: '_filterGroups(fieldGroups, issueType)',
        },
        _fieldGroupMap: {
          type: Object,
          computed: '_computeFieldGroupMap(_filteredGroups)',
          value: () => {},
        },
        _fieldDefsWithGroups: {
          type: Array,
          computed: '_computeFieldDefsWithGroups(fieldDefs, _filteredGroups)',
        },
        _fieldDefsWithoutGroup: {
          type: Array,
          computed: '_computeFieldDefsWithoutGroup(fieldDefs, _fieldGroupMap)',
        },
      };
    }

    static mapStateToProps(state, element) {
      return {
        fieldValueMap: issue.fieldValueMap(state),
        issueType: issue.type(state),
      };
    }

    _valuesForField(fieldValueMap, fieldName, phaseName) {
      if (!fieldValueMap) return [];
      return fieldValueMap.get(
        this._makeFieldValueMapKey(fieldName, phaseName)) || [];
    }

    _makeFieldValueMapKey(fieldName, phaseName) {
      let key = [fieldName];
      if (phaseName) {
        key.push(phaseName);
      }
      return key.join(' ');
    }

    _filterGroups(fieldGroups, issueType) {
      return fieldGroups.filter((group) => {
        if (!group.applicableType) return true;
        return issueType && group.applicableType.toLowerCase()
          === issueType.toLowerCase();
      });
    }

    _computeFieldGroupMap(fieldGroups) {
      return fieldGroups.reduce((acc, group) => {
        return group.fieldNames.reduce((acc, fieldName) => {
          acc[fieldName] = group.groupName;
          return acc;
        }, acc);
      }, {});
    }

    _computeFieldDefsWithGroups(fieldDefs, fieldGroups) {
      if (!fieldDefs) return [];
      let groups = [];
      fieldGroups.forEach((group) => {
        let groupFields = [];
        group.fieldNames.forEach((name) => {
          const fd = fieldDefs.find(
            (fd) => (fd.fieldRef.fieldName == name));
          if (fd) {
            groupFields.push(fd);
          }
        });
        if (groupFields.length > 0) {
          groups.push({
            groupName: group.groupName,
            fieldDefs: groupFields,
          });
        }
      });
      return groups;
    }

    _computeFieldDefsWithoutGroup(fieldDefs, fieldGroupMap) {
      if (!fieldDefs) return [];
      return fieldDefs.filter((fd) => {
        return !(fd.fieldRef.fieldName in fieldGroupMap);
      });
    }
  };
};
