// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// TODO(zhangtiff): Remove this hardcoded data once backend custom
// field grouping is implemented. http://crbug.com/monorail/4549
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

export const fieldGroupMap = (fieldGroupsArg, issueType) => {
  const fieldGroups = groupsForType(fieldGroupsArg, issueType);
  return fieldGroups.reduce((acc, group) => {
    return group.fieldNames.reduce((acc, fieldName) => {
      acc[fieldName] = group.groupName;
      return acc;
    }, acc);
  }, {});
};

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
  return key.join(' ').toLowerCase();
};

export const groupsForType = (fieldGroups, issueType) => {
  return fieldGroups.filter((group) => {
    if (!group.applicableType) return true;
    return issueType && group.applicableType.toLowerCase()
      === issueType.toLowerCase();
  });
};

export const fieldDefsWithGroup = (fieldDefs, fieldGroupsArg, issueType) => {
  const fieldGroups = groupsForType(fieldGroupsArg, issueType);
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

export const fieldDefsWithoutGroup = (fieldDefs, fieldGroups, issueType) => {
  if (!fieldDefs) return [];
  const map = fieldGroupMap(fieldGroups, issueType);
  return fieldDefs.filter((fd) => {
    return !(fd.fieldRef.fieldName in map);
  });
};
