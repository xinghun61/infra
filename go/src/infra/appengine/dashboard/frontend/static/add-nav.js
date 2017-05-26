// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window) {
  'use strict';

  function addPrevNext(dateCenterUTC) {
    let dateCenterLocal = new Date(dateCenterUTC);
    let tsPrev = getTimeStamps(dateCenterLocal, -7);
    let tsNext;
    // A page showing the latest 7 days should not have a 'Newer' link
    if (!sameDay(dateCenterLocal, new Date())) {
      tsNext = getTimeStamps(dateCenterLocal, 7);
    }

    document.querySelectorAll('.js-older-link').forEach(olderLink => {
      let link = document.createElement('a');
      link.textContent = 'Older';
      link.href = `?upto=${tsPrev}`;
      olderLink.appendChild(link);
    });
    document.querySelectorAll('.js-newer-link').forEach(newerLink => {
      if (tsNext === undefined) {
	newerLink.style.display = 'none';
      } else {
	let link = document.createElement('a');
	link.textContent = 'Newer';
	link.href = `?upto=${tsNext}`;
	newerLink.appendChild(link);
      }
    });
  }

  function getTimeStamps(baseDate, diff) {
    let date = new Date(baseDate);
    date.setDate(date.getDate() + diff);
    // A link should never take the user to a page showing days that
    // haven't happend yet.
    if (date > new Date()) {
      date = new Date();
    }
    date.setHours(23, 59, 59, 0);
    return date.getTime() / 1000;
  }

  // sameDate should be used to check if two Date objects occur within
  // the same day. Simply comparing the two objects would be too granular
  // as Date objects also include the time within a day.
  function sameDay(d1, d2) {
    return d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate();
  }

  window.__addPrevNext = window.__addPrevNext || addPrevNext;
})(window);
