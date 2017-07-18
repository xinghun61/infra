/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview Simple functions for dismissible on-page help ("cues").
 */

/**
 * Dimisses the cue.  This both updates the DOM and hits the server to
 * record the fact that the user has dismissed it, so that it won't
 * be shown again.
 *
 * If no security token is present, only the DOM is updated and
 * nothing is recorded on the server.
 *
 * @param {string} cueId The identifier of the cue to hide.
 * @return {boolean} false to cancel any event.
 */
function CS_dismissCue(cueId) {
  var cueElements = document.querySelectorAll('.cue');
  for (var i = 0; i < cueElements.length; ++i) {
    cueElements[i].style.display = 'none';
  }

  if (CS_env.token) {
    CS_setCue(cueId);
  }
  return false;
}

/**
 * Function to communicate with the server to record the fact that the
 * user has dismissed a cue.  This just passes an object through to the
 * cues servlet as key-value pairs.
 *
 * @param {string} cueId The identifier of the cue to hide.
 */
function CS_setCue(cueId) {
  var setCueUrl = '/hosting/cues.do';

  // Ignore the response, since we can't do anything about failures.
  CS_doPost(setCueUrl, null, {'cue_id': cueId});
}

// Exports
_CS_dismissCue = CS_dismissCue;
