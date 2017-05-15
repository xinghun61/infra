// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window) {
  const STATUS_URL = 'https://infra-status.appspot.com/current?format=json';
  const UNKNOWN_DATE = new Date(0);
  const REQUEST_STATUS_SUCCESS = 200;

  /**
   * Placeholder status when we're waiting for an answer.
   */
  const PENDING_TREE_STATUS = {
    isOpen: false,
    generalState: 'unknown',
    message: 'Waiting for tree status...',
    username: 'Pending',
    date: UNKNOWN_DATE,
  };
  const REQUEST_ERROR_STATUS = {
    isOpen: false,
    generalState: 'unknown',
    message: "Error occured while requesting tree status",
    username: 'RequestError',
    date: UNKNOWN_DATE
  };

  /**
   * Holds information for requesting the tree status.
   */
  function StatusFetcher() {
    this.statusURL = STATUS_URL;
    this.lastKnownStatus = PENDING_TREE_STATUS;
  }

  /**
   * Asynchronously fetches the tree status and calls the callback.
   */
  StatusFetcher.prototype.fetch = function () {
    this.renderStatus();
    fetch(this.statusURL).then(response => {
      if (response.status === REQUEST_STATUS_SUCCESS) {
	response.json().then(data => {
	  this.onFetchCompleted(data);
	});
      }
    }).catch(err => {
      this.lastKnownStatus = REQUEST_ERROR_STATUS;
      this.renderStatus();
    });
  }

  /**
   * Called when HTTP request finishes (successfully or not).
   * @param {Object} request Completed XMLHttpRequest object.
   */
  StatusFetcher.prototype.onFetchCompleted = function(data) {
    let treeStatus = {
      isOpen: data.can_commit_freely,
      generalState: data.general_state,
      message: data.message,
      username: data.username,
      date: new Date(data.date.replace(' ', 'T'))
    };
    this.lastKnownStatus = treeStatus;
    this.renderStatus();
  }

  /**
   * Uses the latest status information to render the tree status UI.
   */
  StatusFetcher.prototype.renderStatus = function() {
    let statusHeader = document.querySelector('.js-tree');
    let status = this.lastKnownStatus;
    if (status.isOpen) {
      statusHeader.classList.remove('tree-closed');
      statusHeader.classList.add('tree-open');
    } else {
      statusHeader.classList.remove('tree-open');
      statusHeader.classList.add('tree-closed');
    }
    document.querySelector('.js-tree-message').textContent = status.message;
    let treeStatus =
	`Tree is ${status.generalState}. ${status.date} ${status.username}:`
    document.querySelector('.js-tree-status').textContent = treeStatus;
  }

  window.__StatusFetcher = window.__StatusFetcher || StatusFetcher;
})(window);
