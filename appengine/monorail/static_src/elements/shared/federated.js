// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Logic for dealing with federated issue references.
 */

const GOOGLE_ISSUE_TRACKER_REGEX = /^b\/\d+$/;

// Returns if shortlink is valid for any federated tracker.
export function isShortlinkValid(shortlink) {
  return FEDERATED_TRACKERS.some((TrackerClass) => {
    try {
      return new TrackerClass(shortlink);
    } catch (e) {
      return false;
    }
  });
}

// Returns a issue instance for the first matching tracker.
export function fromShortlink(shortlink) {
  for (const key in FEDERATED_TRACKERS) {
    if (FEDERATED_TRACKERS.hasOwnProperty(key)) {
      const TrackerClass = FEDERATED_TRACKERS[key];
      try {
        return new TrackerClass(shortlink);
      } catch (e) {
        continue;
      }
    }
  }
  return null;
}

// FederatedIssue is an abstract class for representing one federated issue.
// Each supported tracker should subclass this class.
class FederatedIssue {
  constructor(shortlink) {
    if (!this.isShortlinkValid(shortlink)) {
      throw new Error(`Invalid shortlink for tracker: ${shortlink}`);
    }
    this.shortlink = shortlink;
  }

  // isShortlinkValid returns whether a given shortlink is valid.
  isShortlinkValid(shortlink) {
    if (!(typeof shortlink === 'string')) {
      throw new Error('shortlink argument must be a string.');
    }
    return Boolean(shortlink.match(this.shortlinkRe()));
  }

  // shortlinkRe returns the regex used to validate shortlinks.
  shortlinkRe() {
    throw new Error('Not implemented.');
  }

  // toURL returns the URL to this issue.
  toURL() {
    throw new Error('Not implemented.');
  }
}

export class GoogleIssueTrackerIssue extends FederatedIssue {
  constructor(shortlink) {
    super(shortlink);
    this.issueID = Number(shortlink.substr(2));
  }

  shortlinkRe() {
    return GOOGLE_ISSUE_TRACKER_REGEX;
  }

  toURL() {
    return `https://issuetracker.google.com/issues/${this.issueID}`;
  }
}

// A list of supported tracker classes.
const FEDERATED_TRACKERS = [
  GoogleIssueTrackerIssue,
];
