/* Copyright 2017 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * Shows the given message via <app-messages>.
 *
 * @param {number} messageId The ID of a predefined message in <app-messages>.
 * @param {string} content The content of the customized message.
 * @param {string} titile The title for the predefined or customized message.
 * @param {boolean} preFormat If true, show the message in a <pre> tag.
 */
function displayMessage(messageId, content, title, preFormat) {
  var detail = {
    'messageId': messageId,
    'content': content,
    'title': title,
    'preFormat': preFormat,
  };
  var event = new CustomEvent('message', {'detail': detail});
  console.log('Dispatching message event:');
  console.log(event);
  document.dispatchEvent(event);
}
