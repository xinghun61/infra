/* Copyright 2018 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import MonorailTSMon from './monorail-ts-mon.js';

/*
ClientLogger is a JavaScript library for tracking events with Google Analytics
and ts_mon.

Example usage (tracking time to create a new issue, including time spent
by the user editing stuff):

t0: on page load for /issues/new:

  let l = new Clientlogger('issues');
  l.logStart('new-issue', 'user-time');

t1: on submit for /issues/new (POST /issues/detail_ezt.do):

  l.logStart('new-issue', 'server-time');

t2: on page load for /issues/detail:

  let l = new Clientlogger('issues');
  if (l.started('new-issue') {
    l.logEnd('new-issue');
  }

This would record the following metrics:

  issues.new-issue {
    time: t2-t0
  }

  issues.new-issue["server-time"] {
    time: t2-t1
  }

  issues.new-issue["user-time"] {
    time: t1-t0
  }
*/

export default class ClientLogger {
  constructor(category) {
    this.category = category;
    this.tsMon = MonorailTSMon.getGlobalClient();

    const categoryKey = `ClientLogger.${category}.started`;
    const startedEvtsStr = sessionStorage[categoryKey];
    if (startedEvtsStr) {
      this.startedEvents = JSON.parse(startedEvtsStr);
    } else {
      this.startedEvents = {};
    }
  }

  started(eventName) {
    return this.startedEvents[eventName];
  }

  // One-shot events
  logEvent(eventAction, eventLabel, opt_eventValue) {
    ga('send', 'event', this.category, eventAction, eventLabel,
        opt_eventValue);
  }

  // Events that bookend some activity whose duration we’re interested in.
  logStart(eventName, eventLabel) {
    // Tricky situation: initial new issue POST gets rejected
    // due to form validation issues.  Start a new timer, or keep
    // the original?

    const startedEvent = this.startedEvents[eventName] || {
      time: new Date().getTime(),
    };

    if (eventLabel) {
      if (!startedEvent.labels) {
        startedEvent.labels = {};
      }
      startedEvent.labels[eventLabel] = new Date().getTime();
    }

    this.startedEvents[eventName] = startedEvent;

    sessionStorage[`ClientLogger.${this.category}.started`] =
        JSON.stringify(this.startedEvents);

    this.logEvent(`${eventName}-start`, eventLabel);
  }

  // Pause the stopwatch for this event.
  logPause(eventName, eventLabel) {
    if (!eventLabel) {
      throw `logPause called for event with no label: ${eventName}`;
    }

    const startEvent = this.startedEvents[eventName];

    if (!startEvent) {
      console.warn(`logPause called for event with no logStart: ${eventName}`);
      return;
    }

    if (!startEvent.labels[eventLabel]) {
      console.warn(`logPause called for event label with no logStart: ` +
        `${eventName}.${eventLabel}`);
      return;
    }

    const elapsed = new Date().getTime() - startEvent.labels[eventLabel];
    if (!startEvent.elapsed) {
      startEvent.elapsed = {};
      startEvent.elapsed[eventLabel] = 0;
    }

    // Save accumulated time.
    startEvent.elapsed[eventLabel] += elapsed;

    sessionStorage[`ClientLogger.${this.category}.started`] =
        JSON.stringify(this.startedEvents);
  }

  // Resume the stopwatch for this event.
  logResume(eventName, eventLabel) {
    if (!eventLabel) {
      throw `logResume called for event with no label: ${eventName}`;
    }

    const startEvent = this.startedEvents[eventName];

    if (!startEvent) {
      console.warn(`logResume called for event with no logStart: ${eventName}`);
      return;
    }

    if (!startEvent.hasOwnProperty('elapsed')
        || !startEvent.elapsed.hasOwnProperty(eventLabel)) {
      console.warn(`logResume called for event that was never paused:` +
        `${eventName}.${eventLabel}`);
      return;
    }

    // TODO(jeffcarp): Throw if an event is resumed twice.

    startEvent.labels[eventLabel] = new Date().getTime();

    sessionStorage[`ClientLogger.${this.category}.started`] =
        JSON.stringify(this.startedEvents);
  }

  logEnd(eventName, eventLabel, maxThresholdMs=null) {
    const startEvent = this.startedEvents[eventName];

    if (!startEvent) {
      console.warn(`logEnd called for event with no logStart: ${eventName}`);
      return;
    }

    // If they've specified a label, report the elapsed since the start
    // of that label.
    if (eventLabel) {
      if (!startEvent.labels.hasOwnProperty(eventLabel)) {
        console.warn(`logEnd called for event + label with no logStart: ` +
          `${eventName}/${eventLabel}`);
        return;
      }

      this._sendTiming(startEvent, eventName, eventLabel, maxThresholdMs);

      delete startEvent.labels[eventLabel];
      if (startEvent.hasOwnProperty('elapsed')) {
        delete startEvent.elapsed[eventLabel];
      }
    } else {
      // If no label is specified, report timing for the whole event.
      this._sendTiming(startEvent, eventName, null, maxThresholdMs);

      // And also end and report any labels they had running.
      for (const label in startEvent.labels) {
        this._sendTiming(startEvent, eventName, label, maxThresholdMs);
      }

      delete this.startedEvents[eventName];
    }

    sessionStorage[`ClientLogger.${this.category}.started`] =
        JSON.stringify(this.startedEvents);
    this.logEvent(`${eventName}-end`, eventLabel);
  }

  _sendTiming(event, eventName, recordOnlyThisLabel, maxThresholdMs=null) {
    // Calculate elapsed.
    let elapsed;
    if (recordOnlyThisLabel) {
      elapsed = new Date().getTime() - event.labels[recordOnlyThisLabel];
      if (event.elapsed && event.elapsed[recordOnlyThisLabel]) {
        elapsed += event.elapsed[recordOnlyThisLabel];
      }
    } else {
      elapsed = new Date().getTime() - event.time;
    }

    // Return if elapsed exceeds maxThresholdMs.
    if (maxThresholdMs !== null && elapsed > maxThresholdMs) {
      return;
    }

    const options = {
      'timingCategory': this.category,
      'timingVar': eventName,
      'timingValue': elapsed,
    };
    if (recordOnlyThisLabel) {
      options['timingLabel'] = recordOnlyThisLabel;
    }
    ga('send', 'timing', options);
    this.tsMon.recordUserTiming(
        this.category, eventName, recordOnlyThisLabel, elapsed);
  }
}

// Until the rest of the app is in modules, this must be exposed on window.
window.ClientLogger = ClientLogger;
