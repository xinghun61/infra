var actionInfo = {
  patch_start: {
    startAttempt: true,
    description: 'CQ started processing patch',
    cls: 'important',
  },
  patch_stop: {
    stopAttempt: true,
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
  'not started',
];


function main() {
  container.textContent = 'Loading patch data...';
  loadPatchsetRecords(function(records) {
    displayRecords(records);
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

function displayRecords(records) {
  container.textContent = '';
  var currentAttempt = null;
  var attempts = [];
  records.forEach(function(record) {
    var action = record.fields.action;
    var info = actionInfo[action];
    if (typeof info === 'function') {
      info = info(record);
    }
    if (!info || (info.filter && !info.filter(record))) {
      return;
    }
    if (info.startAttempt) {
      currentAttempt = {
        start: record.timestamp,
        header: newHeader(attempts.length + 1),
        rows: [],
      }
      attempts.push(currentAttempt);
    }
    if (!currentAttempt) {
      console.warn('Unexpected record outside of start/end records:', record);
    }
    var duration = getDurationString(currentAttempt.start, record.timestamp);
    currentAttempt.rows.push(newRow(record.timestamp, duration, info.description, record.fields.message, info.cls));
    if (info.stopAttempt) {
      currentAttempt.header.addText(' (' + duration + ')');
      currentAttempt = null;
    }
  });
  if (currentAttempt) {
    currentAttempt.header.addText(' (in progress for ' + getDurationString(currentAttempt.start, Date.now() / 1000) + ')');
  }
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

function newHeader(attemptNumber) {
  var header = newElement('h3');
  var anchor = newElement('a', 'Attempt #' + attemptNumber);
  anchor.name = attemptNumber;
  anchor.href = '#' + attemptNumber;
  header.appendChild(anchor);
  header.addText = function(text) {
    anchor.textContent += text;
  };
  return header;
}

function newRow(timestamp, duration, description, message, cls) {
  var row = newElement('row', '', cls);
  row.appendChild(newElement('timestamp', getTimestampString(timestamp)));
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

function getTimestampString(timestamp) {
  return new Date(timestamp * 1000).toISOString().replace('T', ' ').slice(0, 19);
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

function startedJobsInfo(record) {
  var jobs = record.fields.tryjobs;
  var node = newElement('div');
  var builders = [];
  for (var master in jobs) {
    for (builder in jobs[master]) {
      builders.push(builder);
    }
  }
  builders.sort();
  node.appendChild(newElement('span', 'Tryjob' + plural(builders.length) + ' triggered: '))
  builders.forEach(function(builder) {
    node.appendChild(newElement('tryjob', builder, 'triggered'));
    node.appendChild(newElement('span', ' '));
  });

  return {
    description: node,
    cls: 'normal',
    filter: simpleTryjobVerifierCheck,
  };
}

function jobsUpdateInfo(record) {
  var jobs = record.fields.jobs;
  var node = newElement('div');
  var firstLine = true;
  for (var status = 0; status < tryjobStatus.length; status++) {
    var builderURLs = {};
    for (var master in jobs) {
      for (builder in jobs[master]) {
        var data = jobs[master][builder];
        if (data.status === status) {
          builderURLs[builder] = data.rietveld_results.length > 0 ? data.rietveld_results[0].url : null;
        }
      }
    }
    var builders = Object.getOwnPropertyNames(builderURLs).sort();
    if (builders.length === 0) {
      continue;
    }
    if (!firstLine) {
      node.appendChild(newElement('br'));
    }
    firstLine = false;
    node.appendChild(newElement('span', 'Tryjob' + plural(builders.length) + ' ' + tryjobStatus[status] + ': '))
    builders.forEach(function(builder) {
      var url = builderURLs[builder];
      var bubble = newElement('tryjob', '', tryjobStatus[status].replace(' ', '-'));
      if (url) {
        var a = newElement('a', builder);
        a.href = url;
        bubble.appendChild(a);
      } else {
        bubble.textContent = builder;
      }
      node.appendChild(bubble);
      node.appendChild(newElement('span', ' '));
    });
  }

  return firstLine ? null : {
    description: node,
    cls: 'normal',
    filter: simpleTryjobVerifierCheck,
  };
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
