// Variables for console Javascript access to the currently visible/selected records.
var records = [];
var selectedRecords = [];

(function(){
'use strict';

var indexSelected = {};
var logServer = '//chromium-cq-status.appspot.com';
var reviewServer = '//codereview.chromium.org';
var tags = [];
var cursor = null;

function main() {
  loadTags();
  loadMore.addEventListener('click', loadNextQuery);
  window.addEventListener('hashchange', loadTags);
}

function loadTags() {
  var hash = window.location.hash.slice(1);
  tags = hash ? hash.split(',') : [];
  cursor = null;
  clearTable();
  loadNextQuery();
  updateFilterList();
}

function clearTable() {
  records = [];
  selectedRecords = [];
  indexSelected = {};
  [].forEach.call(table.querySelectorAll('tr ~ tr'), function(row) {
    row.remove();
  });
}

function loadNextQuery() {
  loading.classList.remove('hide');
  loadMore.disabled = true;
  loadJSON(nextURL(), function(json) {
    loading.classList.add('hide');
    cursor = json.more ? json.cursor : null;
    loadMore.disabled = !cursor;
    json.results.forEach(addRow);
  });
}

function nextURL() {
  var url = logServer + '/query';
  var params = [];
  if (tags.length > 0) {
    params.push('tags=' + tags.join(','));
  }
  if (cursor) {
    params.push('cursor=' + cursor);
  }
  if (params.length) {
    url += '?' + params.join('&');
  }
  return url;
}

function loadJSON(url, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('get', url, true);
  xhr.responseType = 'json';
  xhr.onload = function() {
    callback(xhr.response);
  };
  xhr.send();
}

function addRow(record) {
  var index = records.length;
  records.push(record);
  var row = newElement('tr');
  var items = [
    newElement('span', new Date(record.timestamp * 1000)),
    newFieldValue(record, 'project'),
    newFieldValue(record, 'owner'),
    newFieldValue(record, 'issue'),
    newFieldValue(record, 'patchset'),
    newFieldValue(record, 'action'),
    newFieldValue(record, 'verifier'),
    newFieldValue(record, 'message'),
    newDetailLinks(record),
  ];
  items.forEach(function(item) {
    var cell = newElement('td');
    cell.appendChild(item);
    row.appendChild(cell);
  });
  row.addEventListener('click', function(event) {
    if (event.target.tagName !== 'A') {
      row.classList.toggle('selected');
      indexSelected[index] = !indexSelected[index];
      updateSelectedRecords();
    }
  })
  table.appendChild(row);
}

function newFieldValue(record, field) {
  var value = record.fields[field];
  var tag = field + '=' + value;
  if (record.tags.indexOf(tag) !== -1 && tags.indexOf(tag) === -1) {
    return newLink(value, '#' + tags.concat([tag]).join(','));
  }
  return newElement('span', value);
}

function newDetailLinks(record) {
  var span = newElement('span');
  span.appendChild(newJsonDialogLink(record));
  var statusLink = newStatusLink(record.fields);
  if (statusLink) {
    span.appendChild(newElement('span', ' '));
    span.appendChild(statusLink);
  }
  var reviewLink = newReviewLink(record.fields);
  if (reviewLink) {
    span.appendChild(newElement('span', ' '));
    span.appendChild(reviewLink);
  }
  return span;
}

function newJsonDialogLink(record) {
  var a = newLink('[json]');
  a.addEventListener('click', function(event) {
    event.preventDefault();
    a.href = '';
    var dialog = newElement('dialog');
    var textarea = newElement('textarea', JSON.stringify(record, null, '  '));
    textarea.selectionStart = textarea.selectionEnd = 0;
    textarea.addEventListener('click', function(event) {
      event.stopPropagation();
    });
    dialog.appendChild(textarea);
    dialog.addEventListener('click', function() {
      dialog.remove();
    });
    document.body.appendChild(dialog);
    dialog.showModal();
  });
  return a;
}

function newStatusLink(fields) {
  if (!fields.issue || !fields.patchset) {
    return null;
  }
  return newLink('[status]', logServer + '/patch-status/' + fields.issue + '/' + fields.patchset);
}

function newReviewLink(fields) {
  if (!fields.issue) {
    return null;
  }
  var patchset = fields.patchset ? '#ps' + fields.patchset : '';
  return newLink('[review]', reviewServer + '/' + fields.issue + patchset);
}

function updateFilterList() {
  if (tags.length === 0) {
    filterList.textContent = 'None';
    return;
  }
  filterList.textContent = '';
  tags.forEach(function(tag, i) {
    var otherTags = tags.slice();
    otherTags.splice(i, 1);
    i && filterList.appendChild(newElement('span', ', '));
    filterList.appendChild(newLink(tag, '#' + otherTags.join(',')));
  })
  filterList.appendChild(newElement('span', ' '));
  var a = newElement('a', '[clear all]');
  a.href = '';
  filterList.appendChild(a);
}

function newLink(text, url) {
  var a = newElement('a', text);
  a.href = url ? url : '//';
  return a;
}

function newElement(tag, text) {
  var element = document.createElement(tag);
  if (text) {
    element.textContent = text;
  }
  return element;
}

function updateSelectedRecords() {
  selectedRecords = [];
  for (var i in indexSelected) {
    if (indexSelected[i]) {
      selectedRecords.push(records[i]);
    }
  }
}

window.addEventListener('load', main);

})();
