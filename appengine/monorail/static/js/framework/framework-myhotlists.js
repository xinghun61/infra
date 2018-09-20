/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview This file initializes the "My Hotlists" drop down menu in the
 *     user bar. It utilizes the menu widget defined in framework-menu.js.
 */

/** @type {Menu} */
var myhotlists;

(function() {
  var target = document.getElementById('hotlists-dropdown');

  if (!target) {
    return;
  }

  myhotlists = new Menu(target, function() {});

  myhotlists.addEvent(window, 'load', CS_updateHotlists);
  myhotlists.addOnOpen(CS_updateHotlists);
  myhotlists.addEvent(window, 'load', function() {
    document.body.appendChild(myhotlists.menu);
  });
})();


/**
 * Grabs the list of logged in user's hotlists to populate the "My Hotlists"
 * drop down menu.
 */
async function CS_updateHotlists() {
  if (!myhotlists) return;

  if (!window.CS_env.loggedInUserEmail) {
    myhotlists.clear();
    myhotlists.addItem('sign in to see your hotlists',
                       window.CS_env.login_url,
                       'controls');
    return;
  }

  const ownedHotlistsMessage = {
    user: {
      display_name: window.CS_env.loggedInUserEmail,
    }};

  const responses = await Promise.all([
    window.prpcClient.call(
      'monorail.Features', 'ListHotlistsByUser', ownedHotlistsMessage),
    window.prpcClient.call(
      'monorail.Features', 'ListStarredHotlists', {}),
    window.prpcClient.call(
      'monorail.Features', 'ListRecentlyVisitedHotlists', {}),
  ]);
  const ownedHotlists = responses[0];
  const starredHotlists = responses[1];
  const visitedHotlists = responses[2];

  myhotlists.clear();

  const sortByName = (hotlist1, hotlist2) => {
    hotlist1.name.localeCompare(hotlist2.name);
  };

  if (ownedHotlists.hotlists) {
    ownedHotlists.hotlists.sort(sortByName);
    ownedHotlists.hotlists.forEach(hotlist => {
      const name = hotlist.name;
      const userId = hotlist.ownerRef.userId;
      const url = `/u/${userId}/hotlists/${name}`;
      myhotlists.addItem(name, url, 'hotlists', 'Hotlists');
    });
  }

  if (starredHotlists.hotlists) {
    myhotlists.addSeparator();
    starredHotlists.hotlists.sort(sortByName);
    starredHotlists.hotlists.forEach(hotlist => {
      const name = hotlist.name;
      const userId = hotlist.ownerRef.userId;
      const url = `/u/${userId}/hotlists/${name}`;
      myhotlists.addItem(name, url, 'starred_hotlists', 'Starred Hotlists');
    });
  }

  if (visitedHotlists.hotlists) {
    myhotlists.addSeparator();
    visitedHotlists.hotlists.sort(sortByName);
    visitedHotlists.hotlists.forEach(hotlist => {
      const name = hotlist.name;
      const userId = hotlist.ownerRef.userId;
      const url = `/u/${userId}/hotlists/${name}`;
      myhotlists.addItem(
          name, url, 'visited_hotlists', 'Recently Visited Hotlists');
    });
  }

  myhotlists.addSeparator();
  myhotlists.addItem(
      'All hotlists', `/u/${window.CS_env.loggedInUserEmail}/hotlists`,
      'controls');
  myhotlists.addItem('Create hotlist', '/hosting/createHotlist', 'controls');
}
