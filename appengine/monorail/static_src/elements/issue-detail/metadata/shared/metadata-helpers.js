// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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

export const fieldGroupMap = (fieldGroups) => {
  return fieldGroups.reduce((acc, group) => {
    return group.fieldNames.reduce((acc, fieldName) => {
      acc[fieldName] = group.groupName;
      return acc;
    }, acc);
  }, {});
};

export const FIELD_GROUP_MAP = fieldGroupMap(HARDCODED_FIELD_GROUPS);

export const valuesForField = (fieldValueMap, fieldName, phaseName) => {
  if (!fieldValueMap) return [];
  return fieldValueMap.get(
    fieldValueMapKey(fieldName, phaseName)) || [];
};

export const fieldValueMapKey = (fieldName, phaseName) => {
  const key = [fieldName];
  if (phaseName) {
    key.push(phaseName);
  }
  return key.join(' ');
};

export const groupsForType = (fieldGroups, issueType) => {
  return fieldGroups.filter((group) => {
    if (!group.applicableType) return true;
    return issueType && group.applicableType.toLowerCase()
      === issueType.toLowerCase();
  });
};

export const fieldDefsWithGroup = (fieldDefs, fieldGroupsArg) => {
  const fieldGroups = fieldGroupsArg || HARDCODED_FIELD_GROUPS;
  if (!fieldDefs) return [];
  const groups = [];
  fieldGroups.forEach((group) => {
    const groupFields = [];
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
};

export const fieldDefsWithoutGroup = (fieldDefs, fieldMap) => {
  if (!fieldDefs) return [];
  const map = fieldMap || fieldGroupMap(HARDCODED_FIELD_GROUPS);
  return fieldDefs.filter((fd) => {
    return !(fd.fieldRef.fieldName in map);
  });
};
