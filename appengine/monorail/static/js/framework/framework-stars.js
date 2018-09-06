/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS functions that support setting and showing
 * stars throughout Monorail.
 */


/**
 * The character to display when the user has starred an issue.
 */
var TKR_STAR_ON = '\u2605';


/**
 * The character to display when the user has not starred an issue.
 */
var TKR_STAR_OFF = '\u2606';


/**
 * Function to toggle the star on an issue.  Does both an update of the
 * DOM and hit the server to record the star.
 *
 * @param {Element} el The star <a> element.
 * @param {String} projectName name of the project to be starred, or name of
 *                 the project containing the issue to be starred.
 * @param {Integer} localId number of the issue to be starred.
 * @param {String} projectName number of the user to be starred.
 */
function TKR_toggleStar(el, projectName, localId, userId, hotlistId) {
  const starred = (el.textContent.trim() == TKR_STAR_OFF);
  TKR_toggleStarLocal(el);

  const starRequestMessage = {starred: Boolean(starred)};
  if (userId) {
    starRequestMessage.user_ref = {user_id: userId};
    window.prpcClient.call('monorail.Users', 'StarUser', starRequestMessage);
  } else if (projectName && localId) {
    starRequestMessage.issue_ref = {
      project_name: projectName,
      local_id: localId
    };
    window.prpcClient.call('monorail.Issues', 'StarIssue', starRequestMessage);
  } else if (projectName) {
    starRequestMessage.project_name = projectName;
    window.prpcClient.call(
        'monorail.Projects', 'StarProject', starRequestMessage);
  } else if (hotlistId) {
    starRequestMessage.hotlist_ref = {hotlist_id: hotlistId};
    window.prpcClient.call(
        'monorail.Features', 'StarHotlist', starRequestMessage);
  }
}


/**
 * Just update the display state of a star, without contacting the server.
 * Optionally update the value of a form element as well. Useful for when
 * a user is entering a new issue and wants to set its initial starred state.
 * @param {Element} el Star <img> element.
 * @param {string} opt_formElementId HTML ID of the hidden form element for
 *      stars.
 */
function TKR_toggleStarLocal(el, opt_formElementId) {
  var starred = (el.textContent.trim() == TKR_STAR_OFF) ? 1 : 0;

  el.textContent = starred ? TKR_STAR_ON : TKR_STAR_OFF;
  el.style.color = starred ? 'cornflowerblue' : 'grey';
  el.title = starred ? 'You have starred this item' : 'Click to star this item';

  if (opt_formElementId) {
    $(opt_formElementId).value = '' + starred; // convert to string
  }
}


/**
 * When we show two star icons on the same details page, keep them
 * in sync with each other. And, update a message about starring
 * that is displayed near the issue update form.
 * @param {Element} clickedStar The star that the user clicked on.
 * @param {string} otherStarId ID of the other star icon.
 */
function TKR_syncStarIcons(clickedStar, otherStarId) {
  var otherStar = document.getElementById(otherStarId);
  if (!otherStar) {
    return;
  }
  TKR_toggleStarLocal(otherStar);

  var vote_feedback = document.getElementById('vote_feedback');
  if (!vote_feedback) {
    return;
  }

  if (clickedStar.textContent == TKR_STAR_OFF) {
    vote_feedback.textContent =
        'Vote for this issue and get email change notifications.';
  } else {
    vote_feedback.textContent = 'Your vote has been recorded.';
  }
}


// Exports
_TKR_toggleStar = TKR_toggleStar;
_TKR_toggleStarLocal = TKR_toggleStarLocal;
_TKR_syncStarIcons = TKR_syncStarIcons;
