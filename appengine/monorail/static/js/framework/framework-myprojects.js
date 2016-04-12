/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview This file initializes the "My favorites" drop down menu in the
 *     user bar. It utilizes the menu widget defined in framework-menu.js.
 */

/** @type {Menu} */
var myprojects;

(function() {
  var target = document.getElementById('projects-dropdown');

  if (!target) {
    return;
  }

  myprojects = new Menu(target, function() {});

  myprojects.addEvent(window, 'load', CS_updateProjects);
  myprojects.addOnOpen(CS_updateProjects);
  myprojects.addEvent(window, 'load', function() {
      document.body.appendChild(myprojects.menu);
  });
})();

/**
 * Grabs the list of logged in user's projects to populate the "My favorites"
 * drop down menu.
 */
function CS_updateProjects() {
  if (!myprojects) return;
  // Set a request token to prevent XSRF leaking of user project lists.
  if (CS_env.token) {
    var postUrl = '/hosting/projects.do';
    CS_doPost(postUrl, CS_updateProjectsCallback, {});
  } else {
    CS_updateProjectsCallback(null);
  }
}

/**
 * Updates the drop down menu based on the json data received.
 * @param {event} event with xhr Response with JSON data of list of projects.
 */
function CS_updateProjectsCallback(event) {
  var xhr = event ? event.target : null;
  // Grab and show projects if user is signed in
  if (xhr) {
    if (xhr.readyState != 4 || xhr.status != 200)
      return;
    var projects = [];
    var starredProjects = [];

    var json = CS_parseJSON(xhr);
    for (var category in json) {
      switch (category) {
        case 'contributorto':
        case 'memberof':
        case 'ownerof':
          for (var i = 0; i < json[category].length; i++) {
            projects.push(json[category][i]);
          }
          break;

        case 'starred_projects':
          for (var i = 0; i < json[category].length; i++) {
            starredProjects.push(json[category][i]);
          }
          break;

        case 'error':
          return;

        default:
          break;
      }
    }

    myprojects.clear();

    projects.sort();
    for (var i = 0; i < projects.length; i++) {
      var url = '/p/' + projects[i] + '/';
      myprojects.addItem(projects[i], url, 'projects', 'Projects');
    }

    starredProjects.sort();
    for (var i = 0; i < starredProjects.length; i++) {
      var url = '/p/' + starredProjects[i] + '/';
      myprojects.addItem(
          starredProjects[i], url, 'starred_projects', 'Starred projects');
    }

    if (projects.length == 0 && starredProjects.length == 0) {
      // If user has no project memberships then add default control.
      CS_addDefaultControl();
    } else {
      // If there is atleast one project membership then add a 'All projects'
      // link that goes to hosting/
      myprojects.addCategory('---', '---');
      myprojects.addItem('All projects', '/hosting/', '---');
    }

  // Otherwise, ask the user to sign in
  } else {
    myprojects.clear();

    myprojects.addItem(
        'Sign in to see your favorites',
        CS_env['login_url'],
        'controls');

    CS_addDefaultControl();
  }
}

/**
 * Adds default control to the bottom of the "My favorites" menu.
 * It currently adds links to /more and /hosting.
 */
function CS_addDefaultControl() {
  myprojects.addSeparator('controls', '');
  myprojects.addItem('Find projects...', '/hosting/',
                     'controls');
}
