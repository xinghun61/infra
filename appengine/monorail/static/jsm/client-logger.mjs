// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// tsmon-client.js exports its classes onto window.chops.tsmon.
import '/bower_components/chopsui/tsmon-client.js';
const TSMonClient = window.chops.tsmon.TSMonClient;

/*
ClientLogger is a JavaScript library for tracking events with Google Analytics
and ts_mon.

Example usage (tracking time to create a new issue, including time spent
by the user editing stuff):

t0: on page load for /issues/new:

  let l = new Clientlogger('issues');
  l.logStart('new-issue', 'user-time');

t1: on submit for /issues/new (POST /issues/detail.do):

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

export class ClientLogger {
  constructor(category) {
    this.category = category;
    this.ts_mon = new TSMonClient('/_/jstsmon.do', window.CS_env.token);
    this._clientId = ClientLogger.generateClientId();

    this.metrics = [
      {
        category: 'issues',
        eventName: 'issue-update',
        metric: this.ts_mon.cumulativeDistribution(
          'monorail/frontend/issue_update_latency',
          'Latency between issue update form submit and issue detail page load.',
          null,
          (new Map([['client_id', TSMonClient.stringField('client_id')]])),
        ),
      },
      {
        category: 'issues',
        eventName: 'new-issue',
        metric: this.ts_mon.cumulativeDistribution(
          'monorail/frontend/issue_create_latency',
          'Latency between issue entry form submit and issue detail page load.',
          null,
          (new Map([['client_id', TSMonClient.stringField('client_id')]])),
        ),
      },
    ];

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

    let startedEvent = this.startedEvents[eventName] || {
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
      throw `logPause called for event with no logStart: ${eventName}`;
    }

    let elapsed = new Date().getTime() - startEvent.time;
    if (!startEvent.elapsed) {
      startEvent.elapsed = {
        eventLabel: 0
      };
    }

    // Save accumulated time.
    startEvent.elapsed[eventLabel] += elapsed;

    // Reset the start time.
    startEvent.labels[eventLabel] = new Date().getTime();
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
      throw `logResume called for event with no logStart: ${eventName}`;
    }

    startEvent.time = new Date().getTime();

    sessionStorage[`ClientLogger.${this.category}.started`] =
        JSON.stringify(this.startedEvents);
  }

  logEnd(eventName, eventLabel, maxThresholdMs=null) {
    const startEvent = this.startedEvents[eventName];

    if (!startEvent) {
      throw `logEnd called for event with no logStart: ${eventName}`;
    }

    let elapsed = new Date().getTime() - startEvent.time;
    if (startEvent.elapsed && startEvent.elapsed[eventLabel]) {
      elapsed += startEvent.elapsed[eventLabel];
    }

    // If they've specified a label, report the elapsed since the start
    // of that label.
    if (eventLabel) {
      if (startEvent.labels[eventLabel]) {
        elapsed = new Date().getTime() - startEvent.labels[eventLabel];

        if (maxThresholdMs !== null && elapsed > maxThresholdMs) {
          return;
        }

        ga('send', 'timing', {
          'timingCategory': this.category,
          'timingVar': eventName,
          'timingLabel': eventLabel,
          'timingValue': elapsed
        });

        delete startEvent.labels[eventLabel];
      } else {
        throw `logEnd called for event + label with no logStart: ` +
          `${eventName}/${eventLabel}`;
      }
    } else {
      // If no label is specified, report timing for the whole event.
      ga('send', 'timing', {
        'timingCategory': this.category,
        'timingVar': eventName,
        'timingValue': elapsed
      });
      // And also end and report any labels they had running.
      for (let label in startEvent.labels) {
        elapsed = new Date().getTime() - startEvent.labels[label];

        if (maxThresholdMs !== null && elapsed > maxThresholdMs) {
          continue;
        }

        ga('send', 'timing', {
          'timingCategory': this.category,
          'timingVar': eventName,
          'timingLabel': label,
          'timingValue': elapsed
        });
      }

      const metricFields = new Map(Object.entries({
        'client_id': this._clientId,
      }));
      for (let metric of this.metrics) {
        if (this.category === metric.category
            && eventName === metric.eventName) {
          metric.metric.add(elapsed, metricFields);
        }
      }

      delete this.startedEvents[eventName];
    }
    sessionStorage[`ClientLogger.${this.category}.started`] =
        JSON.stringify(this.startedEvents);

    this.logEvent(`${eventName}-end`, eventLabel);
  }

  static generateClientId() {
    /**
     * Returns a random string used as the client_id field in ts_mon metrics.
     *
     * Rationale:
     * If we assume Monorail has sustained 40 QPS, assume every request
     * generates a new ClientLogger (likely an overestimation), and we want
     * the likelihood of a client ID collision to be 0.01% for all IDs
     * generated in any given year (in other words, 1 collision every 10K
     * years), we need to generate a random string with at least 2^30 different
     * possible values (i.e. 30 bits of entropy, see log2(d) in Wolfram link
     * below). Using an unsigned integer gives us 32 bits of entropy, more than
     * enough.
     *
     * Returns:
     *   A string (the base-32 representation of a random 32-bit integer).

     * References:
     * - https://en.wikipedia.org/wiki/Birthday_problem
     * - https://www.wolframalpha.com/input/?i=d%3D40+*+60+*+60+*+24+*+365,+p%3D0.0001,+n+%3D+sqrt(2d+*+ln(1%2F(1-p))),+d,+log2(d),+n
     * - https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/toString
     */
    const randomvalues = new Uint32Array(1);
    window.crypto.getRandomValues(randomvalues);
    return randomvalues[0].toString(32);
  }
}

// Until the rest of the app is in modules, this must be exposed on window.
window.ClientLogger = ClientLogger;
