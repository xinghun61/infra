/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview This file initializes the drop down menu attached
 *     to the signed in user's email address. It utilizes the menu
 *     widget defined in framework-menu.js.
 */

/** @type {Menu} */
var accountMenu;

(function() {
  var target = document.getElementById('account-menu');

  if (!target) {
    return;
  }

  accountMenu = new Menu(target, function() {});
  accountMenu.addItem('Switch accounts', CS_env.login_url);
  accountMenu.addSeparator();
  accountMenu.addItem('Profile', CS_env.profileUrl);
  accountMenu.addItem('Updates', CS_env.profileUrl + 'updates');
  accountMenu.addItem('Settings', '/hosting/settings');
  accountMenu.addItem('Saved queries', CS_env.profileUrl + 'queries');
  accountMenu.addItem('Hotlists', CS_env.profileUrl + 'hotlists');
  accountMenu.addSeparator();
  accountMenu.addItem('Sign out', CS_env.logout_url);

  accountMenu.addEvent(window, 'load', function() {
      document.body.appendChild(accountMenu.menu);
  });
})();
