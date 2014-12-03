var attemptStart = 'patch_start';
var attemptEnd = 'patch_stop';

var actionInfo = {
  patch_start: {
    description: 'CQ started processing patch',
    cls: 'important',
  },
  patch_stop: {
    description: 'CQ stopped processing patch',
    cls: 'important',
  },
  patch_ready_to_commit: {
    description: 'Patch is ready to be committed',
    cls: 'important',
  },
  patch_tree_closed: {
    description: 'Patch blocked on closed tree',
    cls: 'bad',
  },
  patch_throttled: {
    description: 'Patch blocked on throttled CQ',
    cls: 'bad',
  },
  patch_committing: {
    description: 'Patch is being committed',
    cls: 'normal',
  },
  patch_committed: {
    description: 'Patch committed successfully',
    cls: 'good',
  },
  verifier_skip: {
    description: 'Tryjobs skipped',
    cls: 'normal',
    filter: simpleTryjobVerifierCheck,
  },
  verifier_start: startedJobsInfo,
  verifier_jobs_update: jobsUpdateInfo,
  verifier_error: {
    description: 'Error fetching tryjob status',
    cls: 'bad',
    filter: simpleTryjobVerifierCheck,
  },
  verifier_pass: {
    description: 'All tryjobs passed',
    cls: 'good',
    filter: simpleTryjobVerifierCheck,
  },
  verifier_fail: {
    description: 'Patch failed tryjobs',
    cls: 'bad',
    filter: simpleTryjobVerifierCheck,
  },
  verifier_retry: {
    description: 'Retrying failed tryjobs',
    cls: 'bad',
    filter: simpleTryjobVerifierCheck,
  },
  verifier_timeout: {
    description: 'Timeout waiting for tryjob to trigger',
    cls: 'bad',
    filter: simpleTryjobVerifierCheck,
  },
};

tryjobStatus = [
  'passed',
  'failed',
  'running',
  'not-started',
];


function main() {
  container.textContent = 'Loading patch data...';
  loadPatchsetRecords(function(records) {
    displayAttempts(records);
    scrollToHash();
  });
}

function loadPatchsetRecords(callback) {
  var url = '//chromium-cq-status.appspot.com/query/issue=' + issue + '/patchset=' + patchset;
  var records = [];
  var moreRecords = true;
  function queryRecords(cursor) {
    var xhr = new XMLHttpRequest();
    xhr.open('get', url + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''), true);
    xhr.onreadystatechange = function() {
      if (xhr.readyState === XMLHttpRequest.DONE) {
        response = JSON.parse(xhr.responseText);
        records = records.concat(response.results);
        if (response.more) {
          queryRecords(response.cursor);
        } else {
          records.reverse();
          callback(records);
        }
      }
    }
    xhr.send();
  }
  queryRecords(null);
}

function displayAttempts(records) {
  container.textContent = '';
  var recordGroups = splitByAttempts(records.filter(function(record) { return 'action' in record.fields; }));
  var attempts = [];
  recordGroups.forEach(function(recordGroup, i) {
    var lastRecord = recordGroup[recordGroup.length - 1];
    var attempt = {
      number: i + 1,
      start: recordGroup[0].timestamp,
      ended: lastRecord.fields.action == attemptEnd,
      lastUpdate: lastRecord.timestamp,
      tryjobs: {},
      rows: [],
      header: null,
    };
    recordGroup.forEach(function(record) {
      var info = actionInfo[record.fields.action];
      if (!info) {
        console.warn('Unexpected action ' + record.fields.action + ' at timestamp ' + record.timestamp);
        return;
      }
      if (typeof info === 'function') {
        info = info(attempt, record);
      }
      if (!info || (info.filter && !info.filter(record))) {
        return;
      }
      var duration = getDurationString(attempt.start, record.timestamp);
      attempt.rows.push(newRow(record.timestamp, duration, info.description, record.fields.message, info.cls));
    });
    attempt.header = newHeader(attempt);
    attempts.push(attempt);
  });

  if (attempts.length === 0) {
    container.textContent = 'No attempts found.';
    return;
  }
  attempts.reverse();
  attempts.forEach(function(attempt) {
    container.appendChild(attempt.header);
    attempt.rows.reverse();
    attempt.rows.forEach(function(row) {
      container.appendChild(row);
    });
  });
}

function splitByAttempts(records) {
  var recordGroups = [];
  var recordGroup = null;
  records.forEach(function(record) {
    if (record.fields.action == attemptStart) {
      if (recordGroup) {
        console.warn('Attempt group started before previous one ended.')
      }
      recordGroup = [];
    }
    if (recordGroup) {
      recordGroup.push(record);
    } else {
      console.warn('Attempt record encountered before start signal.')
    }
    if (record.fields.action == attemptEnd) {
      if (recordGroup) {
        recordGroups.push(recordGroup);
      } else {
        console.warn('Attempt group ended before starting.')
      }
      recordGroup = null;
    }
  });
  if (recordGroup) {
    recordGroups.push(recordGroup);
  }
  return recordGroups;
}

function newRow(timestamp, duration, description, message, cls) {
  var row = newElement('row', '', cls);
  row.appendChild(newElement('timestamp', new Date(timestamp * 1000)));
  row.appendChild(newElement('duration', '(' + duration + ')'));
  var descriptionNode = newElement('description')
  if (typeof description === 'string') {
    descriptionNode.textContent = description;
  } else {
    descriptionNode.appendChild(description);
  }
  row.appendChild(descriptionNode);
  if (message) {
    row.appendChild(newElement('message', '(' + message + ')'));
  }
  return row;
}

function newHeader(attempt) {
  var header = newElement('header');

  var h3 = newElement('h3');
  var anchor = newElement('a', 'Attempt #' + attempt.number);
  anchor.name = attempt.number;
  anchor.href = '#' + attempt.number;
  h3.appendChild(anchor);
  header.appendChild(h3);

  if (attempt.ended) {
    header.appendChild(newElement('div', 'Total duration: ' + getDurationString(attempt.start, attempt.lastUpdate)));
  } else {
    header.appendChild(newElement('div', 'In progress for: ' + getDurationString(attempt.start, Date.now() / 1000)));
    header.appendChild(newElement('div', 'Last update: ' + getDurationString(attempt.lastUpdate, Date.now() / 1000) + ' ago'));
  }

  var builders = Object.getOwnPropertyNames(attempt.tryjobs).sort();
  if (builders.length !== 0) {
    header.appendChild(newElement('span', (attempt.ended ? 'Last' : 'Current') + ' tryjob statuses: '));
    builders.forEach(function(builder) {
      header.appendChild(newTryjobBubble(builder, attempt.tryjobs[builder].status, attempt.tryjobs[builder].url));
      header.appendChild(newElement('span', ' '));
    });
    header.appendChild(newElement('br'));
  }

  header.appendChild(newElement('div', 'Status update timeline:'));

  return header;
}

function newElement(tag, text, cls) {
  var element = document.createElement(tag);
  if (text) {
    element.textContent = text;
  }
  if (cls) {
    element.classList.add(cls);
  }
  return element;
}

function getDurationString(startTimestamp, timestamp) {
  var seconds = parseInt(timestamp - startTimestamp);
  if (seconds < 60) {
    return seconds + ' second' + plural(seconds);
  }
  var minutes = parseInt(seconds / 60);
  if (minutes < 60) {
    return minutes + ' minute' + plural(minutes);
  }
  var hours = parseInt(minutes / 60);
  minutes -= hours * 60;
  return hours + ' hour' + plural(hours) + (minutes ? ' ' + minutes + ' minute' + plural(minutes) : '');
}

function plural(value) {
  return value === 1 ? '' : 's';
}

function simpleTryjobVerifierCheck(record) {
  return record.fields.verifier === 'simple try job';
}

function startedJobsInfo(attempt, record) {
  var jobs = record.fields.tryjobs;
  var node = newElement('div');
  var builders = [];
  forEachBuilder(jobs, function(builder) {
    builders.push(builder);
  });
  builders.sort();
  node.appendChild(newElement('span', 'Tryjob' + plural(builders.length) + ' triggered: '))
  builders.forEach(function(builder) {
    node.appendChild(newTryjobBubble(builder, 'triggered'));
    node.appendChild(newElement('span', ' '));
    attempt.tryjobs[builder] = initialTryjobState();
  });

  return {
    description: node,
    cls: 'normal',
    filter: simpleTryjobVerifierCheck,
  };
}

function jobsUpdateInfo(attempt, record) {
  var jobs = record.fields.jobs;
  var node = newElement('div');
  // Update latest attempt tryjob state.
  forEachBuilder(jobs, function(builder, data) {
    if (!attempt.tryjobs[builder]) {
      attempt.tryjobs[builder] = initialTryjobState();
    }
    if ('status' in data) {
      attempt.tryjobs[builder].status = tryjobStatus[data.status];
    }
    if (data.rietveld_results && data.rietveld_results.length > 0) {
      attempt.tryjobs[builder].url = data.rietveld_results[0].url;
    }
  });
  // Scan for status changes to display.
  var firstLine = true;
  tryjobStatus.forEach(function(status) {
    var builders = [];
    forEachBuilder(jobs, function(builder, data) {
      if (tryjobStatus[data.status] === status) {
        builders.push(builder);
      }
    });
    if (builders.length === 0) {
      return;
    }
    if (!firstLine) {
      node.appendChild(newElement('br'));
    }
    firstLine = false;
    node.appendChild(newElement('span', 'Tryjob' + plural(builders.length) + ' ' + status + ': '))
    builders.forEach(function(builder) {
      node.appendChild(newTryjobBubble(builder, status, attempt.tryjobs[builder].url));
      node.appendChild(newElement('span', ' '));
    });
  });

  return firstLine ? null : {
    description: node,
    cls: 'normal',
    filter: simpleTryjobVerifierCheck,
  };
}

function initialTryjobState() {
  return {
    status: 'triggered',
    url: null,
  };
}

function forEachBuilder(jobs, callback) {
  for (var master in jobs) {
    for (var builder in jobs[master]) {
      callback(builder, jobs[master][builder]);
    }
  }
}

function newTryjobBubble(builder, status, url) {
  var bubble = newElement('a', builder, 'tryjob');
  bubble.classList.add(status);
  bubble.title = status;
  if (url) {
    bubble.href = url;
  }
  bubble.addEventListener('mouseenter', bubbleHighlight);
  bubble.addEventListener('mouseleave', bubbleUnhighlight);
  return bubble;
}

function bubbleHighlight(event) {
  [].forEach.call(document.querySelectorAll('a.tryjob[href="' + event.target.href + '"]'), function(bubble) {
    bubble.classList.add('highlight');
  });
}

function bubbleUnhighlight(event) {
  [].forEach.call(document.querySelectorAll('a.tryjob[href="' + event.target.href + '"]'), function(bubble) {
    bubble.classList.remove('highlight');
  });
}

function scrollToHash() {
  if (!location.hash) {
    return;
  }
  var node = document.querySelector('a[name="' + location.hash.slice(1) + '"]');
  var scrollY = 0;
  while (node) {
    scrollY += node.offsetTop;
    node = node.offsetParent;
  }
  window.scrollTo(0, scrollY);
}

window.addEventListener('load', main);
