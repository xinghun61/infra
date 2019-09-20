// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {
  isShortlinkValid,
  fromShortlink,
  GoogleIssueTrackerIssue,
} from './federated.js';
import loadGapi from 'shared/gapi-loader';

describe('isShortlinkValid', () => {
  it('Returns true for valid links', () => {
    assert.isTrue(isShortlinkValid('b/1'));
    assert.isTrue(isShortlinkValid('b/12345678'));
  });

  it('Returns false for invalid links', () => {
    assert.isFalse(isShortlinkValid('b'));
    assert.isFalse(isShortlinkValid('b/'));
    assert.isFalse(isShortlinkValid('b//123456'));
    assert.isFalse(isShortlinkValid('b/123/123'));
    assert.isFalse(isShortlinkValid('b123/123'));
    assert.isFalse(isShortlinkValid('b/123a456'));
  });
});

describe('fromShortlink', () => {
  it('Returns an issue class for valid links', () => {
    assert.instanceOf(fromShortlink('b/1'), GoogleIssueTrackerIssue);
    assert.instanceOf(fromShortlink('b/12345678'), GoogleIssueTrackerIssue);
  });

  it('Returns null for invalid links', () => {
    assert.isNull(fromShortlink('b'));
    assert.isNull(fromShortlink('b/'));
    assert.isNull(fromShortlink('b//123456'));
    assert.isNull(fromShortlink('b/123/123'));
    assert.isNull(fromShortlink('b123/123'));
    assert.isNull(fromShortlink('b/123a456'));
  });
});

describe('GoogleIssueTrackerIssue', () => {
  describe('constructor', () => {
    it('Sets this.shortlink and this.issueID', () => {
      const shortlink = 'b/1234';
      const issue = new GoogleIssueTrackerIssue(shortlink);
      assert.equal(issue.shortlink, shortlink);
      assert.equal(issue.issueID, 1234);
    });

    it('Throws when given an invalid shortlink.', () => {
      assert.throws(() => {
        new GoogleIssueTrackerIssue('b/123/123');
      });
    });
  });

  describe('toURL', () => {
    it('Returns a valid URL.', () => {
      const issue = new GoogleIssueTrackerIssue('b/1234');
      assert.equal(issue.toURL(), 'https://issuetracker.google.com/issues/1234');
    });
  });

  describe('isOpen', () => {
    beforeEach(() => {
      window.CS_env = {gapi_client_id: 'rutabaga'};
      // Pre-load gapi with a fake signin object to prevent loading the
      // real gapi.js.
      loadGapi({
        init: () => {},
        getUserProfileAsync: () => Promise.resolve({}),
      });
    });

    afterEach(() => {
      delete window.CS_env;
    });

    it('Returns a Promise', () => {
      const issue = new GoogleIssueTrackerIssue('b/1234');
      const actual = issue.isOpen();
      assert.instanceOf(actual, Promise);
    });
  });
});
