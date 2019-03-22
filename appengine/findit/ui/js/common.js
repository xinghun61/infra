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
  const detail = {
    'messageId': messageId,
    'content': content,
    'title': title,
    'preFormat': preFormat,
  };
  const event = new CustomEvent('message', {'detail': detail});
  console.log('Dispatching message event:');
  console.log(event);
  document.dispatchEvent(event);
}


/*
 * Shorten the time delta.
 * '2 days, 01:02:03' -> '2 days'
 * '1 day, 01:02:03' -> '1 day'
 * '01:02:03' -> '1 hour'
 * '00:02:03' -> '2 minutes'
 * '00:00:03' -> '3 seconds'
 */
// eslint-disable-line no-unused-vars
function shortenTimeDelta(longTimeDelta) {
  const pattern = /(?:(\d day[s]?),\s)?(\d*):(\d*):(\d*)/;
  // [full match, n day(s), HH, MM, SS]
  const res = longTimeDelta.match(pattern);

  if (typeof(res[1]) != 'undefined') {
    return res[1];
  }

  const timeDeltaParts = {
    2: 'hour',
    3: 'minute',
    4: 'second',
  };

  for (let i=2; i<res.length; i++) {
    const intTimeDelta = parseInt(res[i]);
    if ( intTimeDelta == 1) {
      return intTimeDelta + ' ' + timeDeltaParts[i];
    }
    if ( intTimeDelta > 1) {
      return intTimeDelta + ' ' + timeDeltaParts[i] + 's';
    }
  }
  return 'just now';
}
