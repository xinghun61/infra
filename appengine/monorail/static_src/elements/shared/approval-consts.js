// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

export const APPROVER_RESTRICTED_STATUSES = new Set(
    ['NA', 'Approved', 'NotApproved']);

export const STATUS_ENUM_TO_TEXT = {
  '': 'NotSet',
  'NEEDS_REVIEW': 'NeedsReview',
  'NA': 'NA',
  'REVIEW_REQUESTED': 'ReviewRequested',
  'REVIEW_STARTED': 'ReviewStarted',
  'NEED_INFO': 'NeedInfo',
  'APPROVED': 'Approved',
  'NOT_APPROVED': 'NotApproved',
};

export const TEXT_TO_STATUS_ENUM = {
  'NotSet': 'NOT_SET',
  'NeedsReview': 'NEEDS_REVIEW',
  'NA': 'NA',
  'ReviewRequested': 'REVIEW_REQUESTED',
  'ReviewStarted': 'REVIEW_STARTED',
  'NeedInfo': 'NEED_INFO',
  'Approved': 'APPROVED',
  'NotApproved': 'NOT_APPROVED',
};

export const STATUS_CLASS_MAP = {
  'NotSet': 'status-notset',
  'NeedsReview': 'status-notset',
  'NA': 'status-na',
  'ReviewRequested': 'status-pending',
  'ReviewStarted': 'status-pending',
  'NeedInfo': 'status-pending',
  'Approved': 'status-approved',
  'NotApproved': 'status-rejected',
};

export const STATUS_DOCSTRING_MAP = {
  'NotSet': '',
  'NeedsReview': 'Approval gate needs work',
  'NA': 'Approval gate not required',
  'ReviewRequested': 'Approval requested',
  'ReviewStarted': 'Approval in progress',
  'NeedInfo': 'Approval review needs more information',
  'Approved': 'Approved for Launch',
  'NotApproved': 'Not Approved for Launch',
};

export const CLASS_ICON_MAP = {
  'status-na': 'remove',
  'status-notset': 'warning',
  'status-pending': 'autorenew',
  'status-approved': 'done',
  'status-rejected': 'close',
};

export const APPROVAL_STATUSES = Object.keys(STATUS_CLASS_MAP).map(
    (status) => ({status, docstring: STATUS_DOCSTRING_MAP[status], rank: 1}));
