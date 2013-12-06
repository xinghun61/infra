// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
 * Code for the main user-visible status page.
 */

window.onload = function() {
  document.add_new_message.message.focus();
  help_init();
  localize_times();
}

/*
 * Code for dealing with localization of timestamps.
 */

function localize_times() {
  // Localize all the UTC timestamps coming from the server to whatever
  // the user has set in their browser.

  require(["dojo/date/locale"], function(locale) {
    function format(date, datePattern, timePattern) {
      // The dojo guys like to add a sep between the date and the time
      // fields for us (based on locale).  Since we want a standards
      // format, that sep is pure noise, so kill it with {...}.
      // https://bugs.dojotoolkit.org/ticket/17544
      return locale.format(new Date(date), {
          formatLength: 'short',
          datePattern: datePattern + '{',
          timePattern: '}' + timePattern
        }).replace(/{.*}/, ' ');
    }

    function long_date(date) { // RFC2822
      return format(date, 'EEE, dd MMM yyyy', 'HH:mm:ss z');
    }

    function short_date(date) {
      return format(date, 'EEE, dd MMM', 'HH:mm');
    }

    var tzname = locale.format(new Date(), {
        selector: 'time',
        timePattern: 'z'
      });

    var i, elements;

    // Convert all the fields that have a timezone already.
    elements = document.getElementsByName('date.datetz');
    for (i = 0; i < elements.length; ++i)
      elements[i].innerText = long_date(elements[i].innerText);

    // Convert all the fields that lack a timezone (which we know is UTC).
    elements = document.getElementsByName('date.date');
    for (i = 0; i < elements.length; ++i)
      elements[i].innerText = short_date(elements[i].innerText + ' UTC');

    // Convert all the fields that are just a timezone.
    elements = document.getElementsByName('date.tz');
    for (i = 0; i < elements.length; ++i)
      elements[i].innerText = tzname;
  });
}

/*
 * Functions for managing the help text.
 */

function help_init() {
  // Set up the help text logic.
  var message = document.add_new_message.message;
  message.onmouseover = help_show;
  message.onmousemove = help_show;
  message.onmouseout = help_hide;

  var help = document.getElementById('help');
  help.onmouseover = help_show;
  help.onmouseout = help_hide;
}

function help_show() {
  var message = document.add_new_message.message;
  var help = document.getElementById('help');
  help.style.left = message.offsetLeft + 'px';
  help.style.top = message.offsetTop + message.offsetHeight + 'px';
  help.hidden = false;
}

function help_hide() {
  var help = document.getElementById('help');
  help.hidden = true;
}
