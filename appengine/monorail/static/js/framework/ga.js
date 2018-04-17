'use strict';

/*

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

class ClientLogger {
  constructor(category) {
    this.category = category;
    const startedEvtsStr = sessionStorage[`ClientLogger.${category}.started`];
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

  logEnd(eventName, eventLabel) {
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
        ga('send', 'timing', {
          'timingCategory': this.category,
          'timingVar': eventName,
          'timingLabel': label,
          'timingValue': elapsed
        });
      }

      delete this.startedEvents[eventName];
    }
    sessionStorage[`ClientLogger.${this.category}.started`] =
        JSON.stringify(this.startedEvents);

    this.logEvent(`${eventName}-end`, eventLabel);
  }
}


