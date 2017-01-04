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
function CS_updateHotlists() {
  if (!myhotlists) return;

  if (CS_env.token) {
    var postUrl = '/hosting/hotlists.do';
    CS_doPost(postUrl, CS_updateHotlistsCallback, {});
  } else {
    CS_updateHotlistsCallback(null);
  }
}


/**
 * Updates the drop down menu based on the json data received.
 * @param {event} event with xhr Response with JSON data of the list of hotlists.
 */
function CS_updateHotlistsCallback(event) {
  var xhr = event ? event.target : null;
  if (xhr) {
    if (xhr.readyState != 4 || xhr.status != 200){
      return;
    }
    var hotlists = [];
    var starredHotlists = [];

    var json = CS_parseJSON(xhr);
    for (var category in json) {
      switch (category) {
        case 'editorof':
        case 'ownerof':
          for (var i = 0; i < json[category].length; i++) {
            hotlists.push(json[category][i]);
          }
          break;

        case 'starred_hotlists':
          for (var i = 0; i < json[category].length; i++) {
            starredHotlists.push(json[category][i]);
          }
          break;
        case 'user':
          var user = json[category];
          break;
        case 'error':
          return;
        default:
          break;
      }
    }

    myhotlists.clear();

    hotlists.sort();
    for (var i = 0; i < hotlists.length; i++) {
      name = hotlists[i][0];
      url = hotlists[i][1];
      myhotlists.addItem(name, url, 'hotlists', 'Hotlists');
    }

    starredHotlists.sort();
    for (var i = 0; i < starredHotlists.length; i++) {
      name = starredHotlists[i][0];
      url = starredHotlists[i][1];
      myhotlists.addItem(name, url, 'starred_hotlists', 'Starred hotlists');
    }

    if (hotlists.length == 0 && starredHotlists.length == 0) {
      myhotlists.addItem('No hotlists. Create one.', '/u/' + user + '/hotlists', 'controls');
    }
  } else {
    myhotlists.clear();
    myhotlists.addItem('Sign in to see your hotlists',
                       CS_env['login_url'],
                       'controls');
  }
}
