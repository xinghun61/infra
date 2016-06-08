// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window, document) {
  'use strict';

  var el = document.createElement('link');
  el.rel = 'stylesheet';
  el.href = 'https://fonts.googleapis.com/icon?family=Material+Icons';
  el.addEventListener('load', function() { setButtonsVisible(true); });
  document.head.appendChild(el);

  var css = `
    .__crdxFeedbackContainer {
      align-items: center;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      position: fixed;
      bottom: 32px;
      right: 24px;
      z-index: 8675309; /* Jenny */
    }
    .__crdxFeedbackContainer:hover .__crdxFeedbackClose {
      display: block;
    }
    .__crdxFeedbackContainer:hover .__crdxFeedbackAction {
      opacity: 1;
    }
    .__crdxFeedbackButton {
      border-radius: 50%;
      box-shadow: 0 1px 4px rgba(0, 0, 0, .3);
      transition: all .2s;
    }
    .__crdxFeedbackButton:hover {
      box-shadow: 0 2px 2px rgba(0, 0, 0, .2), 0 6px 10px rgba(0, 0, 0, .3);
    }
    .__crdxFeedbackClose::before {
      color: #757575;
      content: 'close';
      display: block;
      font-size: 18px;
      padding: 3px;
    }
    .__crdxFeedbackClose {
      display: none;
      background-color: #fff;
      color: #777;
      cursor: pointer;
      width: 24px;
      height: 24px;
    }
    .__crdxFeedbackAction::before {
      color: #fff;
      display: block;
      padding: 8px;
      content: 'bug_report';
    }
    .__crdxFeedbackAction {
      opacity: .75;
      background-color: #e91e63;
      text-decoration: none;
      margin-top: 8px;
      width: 40px;
      height: 40px;
    }
  `;
  el = document.createElement('style');
  el.appendChild(document.createTextNode(css));
  document.head.appendChild(el);

  var container = document.createElement('div');
  container.classList.add('__crdxFeedbackContainer');
  container.style.display = 'none';

  el = document.createElement('i');
  el.classList.add('material-icons', '__crdxFeedbackButton',
      '__crdxFeedbackClose');
  el.addEventListener('click', function() { setButtonsVisible(false); });
  container.appendChild(el);

  var mainBtn = document.createElement('a');
  mainBtn.classList.add('material-icons', '__crdxFeedbackButton',
      '__crdxFeedbackAction');
  mainBtn.target = '_blank';
  container.appendChild(mainBtn);

  function setButtonsVisible(visible) {
    container.style.display = visible ? null : 'none';
  }
  // document.body may not exist yet.
  if (!document.body) {
    window.addEventListener('load', function() {
      document.body.appendChild(container);
    });
  } else {
    document.body.appendChild(container);
  }

  var crdx = window[window.CrDXObject] || {};
  var queue = crdx.q || [];

  crdx = function() {
    crdx[arguments[0]].apply(null, Array.from(arguments).slice(1));
  };

  crdx.setFeedbackButtonBackgroundColor = function(color) {
    mainBtn.style.backgroundColor = color;
  };

  crdx.setFeedbackButtonLink = function(href) {
    mainBtn.href = href;
  };

  queue.forEach(function(args) { crdx.apply(null, args); });

  window[window.CrDXObject] = crdx;
})(window, document);
