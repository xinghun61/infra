// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
 * Code for the main user-visible status page.
 */

window.onload = function() {
  document.add_new_message.message.focus();
  help_init();
}

/*
 * Functions for managing the help text.
 */

function help_init() {
  // Set up the help text logic.
  var message = document.add_new_message.message;
  message.onmouseover = help_show;
  message.onmousemove = help_show;
  message.onmouseout = help_hide;

  var help = document.getElementById('help');
  help.onmouseover = help_show;
  help.onmouseout = help_hide;
}

function help_show() {
  var message = document.add_new_message.message;
  var help = document.getElementById('help');
  help.style.left = message.offsetLeft + 'px';
  help.style.top = message.offsetTop + message.offsetHeight + 'px';
  help.hidden = false;
}

function help_hide() {
  var help = document.getElementById('help');
  help.hidden = true;
}
