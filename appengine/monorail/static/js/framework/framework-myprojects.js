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
  const userProjectsPromise = window.prpcClient.call(
      'monorail.Projects', 'GetUserProjects', {});
  userProjectsPromise.then(userProjects => {
    // Grab and show projects if user is signed in.
    if (userProjects) {
      const starredProjects = userProjects.starredProjects || [];
      const projects = (userProjects.ownerOf || [])
          .concat(userProjects.memberOf || [])
          .concat(userProjects.contributorTo || []);

      myprojects.clear();

      projects.sort();
      projects.forEach(project => {
        myprojects.addItem(project, `/p/${project}/`, 'projects', 'Projects');
      });

      starredProjects.sort();
      starredProjects.forEach(project => {
        myprojects.addItem(
            project, `/p/${project}/`, 'starred_projects', 'Starred Projects');
      });

      if (projects.length === 0 && starredProjects.length === 0) {
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
  });
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
