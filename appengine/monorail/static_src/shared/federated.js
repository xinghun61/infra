// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Logic for dealing with federated issue references.
 */

import loadGapi from './gapi-loader';

const GOOGLE_ISSUE_TRACKER_REGEX = /^b\/\d+$/;

// Returns if shortlink is valid for any federated tracker.
export function isShortlinkValid(shortlink) {
  return FEDERATED_TRACKERS.some((TrackerClass) => {
    try {
      return new TrackerClass(shortlink);
    } catch (e) {
      if (e instanceof FederatedIssueError) {
        return false;
      } else {
        throw e;
      }
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
        if (e instanceof FederatedIssueError) {
          continue;
        } else {
          throw e;
        }
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
      throw new FederatedIssueError(`Invalid tracker shortlink: ${shortlink}`);
    }
    this.shortlink = shortlink;
  }

  // isShortlinkValid returns whether a given shortlink is valid.
  isShortlinkValid(shortlink) {
    if (!(typeof shortlink === 'string')) {
      throw new FederatedIssueError('shortlink argument must be a string.');
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

  // fetchIssueData must return a Promise that resolves an issue object.
  async fetchIssueData() {
    throw new Error('Not implemented.');
  }
}

export class GoogleIssueTrackerIssue extends FederatedIssue {
  constructor(shortlink) {
    super(shortlink);
    this.issueID = Number(shortlink.substr(2));

    // Pre-emptively load gapi.js so it's available when we need to fetch
    // issue data.
    loadGapi();
  }

  shortlinkRe() {
    return GOOGLE_ISSUE_TRACKER_REGEX;
  }

  toURL() {
    return `https://issuetracker.google.com/issues/${this.issueID}`;
  }

  async fetchIssueData() {
    await loadGapi();
    // TODO(crbug.com/monorail/5856): Implement fetching Buganizer issues.
  }
}


class FederatedIssueError extends Error {}

// A list of supported tracker classes.
const FEDERATED_TRACKERS = [
  GoogleIssueTrackerIssue,
];
