/* milo-bbx-service.js: Transforms Buildbot Json into Milo page structures. */

/*jshint globalstrict: true*/
/*jshint newcap: false*/
/*global Polymer*/
"use strict";

/* General utility functions. */
function getTime(times) {
  /* Turn a buildbot "times" pair into a human readable format.
   *
   * param:
   *   times is expected to be a pair of integers of seconds since utc epoch
   * returns:
   *   Human readable string of the time.  Eg 2 sec, 5 min, 3 hr.
   ***/
  var span = times[1] - times[0];
  if (span < 60) {
    return String(Math.round(span)) + ' sec';
  }
  if (span < 60 * 60) {
    return String(Math.round(span / 60)) + ' min';
  }
  return String(Math.round(span / 3600)) + ' hr';
}


/* Utility functions for converting Buildbot data into Milo components. */
function getStep(step) {
  /* Given a Buildbot step, normalize it into a milo row item.
   * param:
   *   step: Buildbot json for a single step.
   * returns:
   *   A Milo item object.
   ***/
  var status = 'unknown', stdio = '#';
  if (!step.isStarted) {
    status = 'pending';
  } else if (!step.isFinished) {
    status = 'running';
  } else if (!step.results || !step.results[0]) {
    status = 'success';
  } else {
    status = 'failure';
  }

  step.logs.forEach(function(stepLog, i) {
    if (stepLog[0] == 'stdio') {
      stdio = stepLog[1];
    }
  });
  return {
    mainText: step.name,
    status: status,
    url: stdio,
    rightText: getTime(step.times)
  };
}


function getSteps(buildJson) {
  /* Convert a Buildbot build json into a list of Milo items */
  var results = [];
  buildJson.steps.forEach(function(step, i) {
    if (step.name !== 'steps') {
      results.push(getStep(step));
    }
  });
  return results;
}


function getProperties(buildJson) {
  /* Convert a Buildbot build json into a Milo property pane */
  var blamelist = [], revisions = [], others = [], k, v;
  buildJson.properties.forEach(function(prop, i) {
    k = prop[0];
    v = prop[1];
    if (k === "blamelist") {
      return;
    }
    if (k.indexOf("revision") > -1) {
      revisions.push({
        mainText: k,
        bottomleft: v
      });
    } else {
      others.push({
        mainText: k,
        bottomright: v
      });
    }
  });
  return {
    blamelist: blamelist,
    revisions: revisions,
    others: others
  };
}


function getTopbar(buildJson) {
  /* Extract the most important information from a Buildbot json.
   * param:
   *   buildJson: A Buildbot json of a build.
   * returns:
   *   A Milo topbar object.
   ***/
  var results = [], failures = [];
  if (!buildJson.times[1]) {
    results.push({
      mainText: 'Running',
      status: 'running'
    });
  } else if (buildJson.results === undefined || !buildJson.results) {
    results.push({
      mainText: 'This build passed successfully! :D',
      status: 'success'
    });
  } else {
    buildJson.steps.forEach(function(step, i) {
      if (step.results[0] && step.name !== 'steps') {
        failures.push(this.getStep(step));
      }
    });
    results.push({
      isFailure: true,
      failures: failures
    });
  }
  return results;
}


Polymer("milo-bbx-service", {
  created: function () {
    // This contains the full page that will be rendered.
    this.page_root = {};
  },


  getPage: function (buildJson) {
    /* Convert a Buildbot build json into a Milo page tree */
    var topbar = [], steps = [], properties = [];
    if (buildJson) {
      topbar = getTopbar(buildJson);
      steps = getSteps(buildJson);
      properties = getProperties(buildJson);
    }
    return {
      name: this.builder + ' - ' + this.build,
      topbar: topbar,
      steps: steps,
      nav: [
        {name: 'foo'},
        {name: 'bar'},
        {name: 'baz'}],
      properties: properties.others,
      revisions: properties.revisions
    };
  },

  computed: {
    page_root: 'getPage(buildJson)'
  }
});
