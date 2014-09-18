(function(){

function main() {
  loadCQStatsList(function(cqStatsList) {
    container.textContent = '';
    drawGraphs(buildGraphs(cqStatsList));
  });
}

function loadCQStatsList(callback) {
  var url = '//chromium-cq-status.appspot.com/stats/query?project=' + project + '&interval_minutes=' + intervalMinutes;
  var cqStatsList = [];
  var defaultCount = null;
  function queryCQStatsList(cursor) {
    var queryURL = url;
    if (cursor !== null) {
      queryURL += '&cursor=' + encodeURIComponent(cursor);
    }
    if (defaultCount !== null) {
      queryURL += '&count=' + Math.min(defaultCount, dataPoints - cqStatsList.length);
    }
    var xhr = new XMLHttpRequest();
    xhr.open('get', queryURL, true);
    xhr.onreadystatechange = function() {
      if (xhr.readyState === XMLHttpRequest.DONE) {
        response = JSON.parse(xhr.responseText);
        if (!defaultCount) {
          defaultCount = response.results.length;
        }
        cqStatsList = cqStatsList.concat(response.results);
        if (cqStatsList.length < dataPoints && response.more) {
          queryCQStatsList(response.cursor);
        } else {
          cqStatsList.reverse();
          callback(cqStatsList);
        }
      }
    }
    xhr.send();
  }
  queryCQStatsList(null);
}

function buildGraphs(cqStatsList) {
  var graphs = {};
  cqStatsList.forEach(function(cqStats) {
    var date = new Date(cqStats['end'] * 1000);
    cqStats['stats'].forEach(function(stats) {
      ensureGraph(graphs, stats);
      updateGraph(graphs, date, stats);
    });
  });
  return graphs;
}

function ensureGraph(graphs, stats) {
  var name = stats['name'];
  if (!graphs[name]) {
    var graph = {
      type: stats['type'],
      name: stats['name'],
      description: stats['description'],
      rows: [],
    };
    if (graph.type === 'list') {
      graph.unit = stats['unit'];
      graph.multiplier = 1;
      if (graph.unit === 'seconds') {
        graph.unit = 'minutes';
        graph.multiplier = 1 / 60;
      }
    }
    graphs[name] = graph;
  }
}

function updateGraph(graphs, date, stats) {
  var graph = graphs[stats['name']];
  console.assert(stats['type'] == graph.type);
  if (graph.type == 'count') {
    graph.rows.push([
      date,
      stats['count'],
    ]);
  } else if (graph.type === 'list') {
    graph.rows.push([
      date,
      stats['sample_size'],
      stats['max'] * graph.multiplier,
      stats['percentile_99'] * graph.multiplier,
      stats['percentile_90'] * graph.multiplier,
      stats['percentile_50'] * graph.multiplier,
      stats['min'] * graph.multiplier,
      stats['mean'] * graph.multiplier,
    ]);
  } else {
    console.assert(false, 'Unknown type: ' + graph.type);
  }
}

function drawGraphs(graphs) {
  var anyGraphs = false;
  Object.getOwnPropertyNames(graphs).sort().forEach(function(name) {
    anyGraphs = true;
    var title = titleFromName(name);
    var indexLink = createElement('index-link', indexDiv, 'a');
    indexLink.textContent = title;
    indexLink.href = '#' + name;
    createElement('', indexDiv, 'br');
    var graphDiv = createElement('graph', document.body);
    var anchor = createElement('', graphDiv, 'a');
    anchor.name = name;
    var chartDiv = createElement('chart', graphDiv);
    var legendDiv = createElement('legend', graphDiv);
    var graph = graphs[name];
    var options = {
      title: title,
      labels: ['Date'],
      xlabel: graph.description,
      labelsDiv: legendDiv,
      legend: 'always',
      labelsSeparateLines: true,
      highlightSeriesOpts: {
        strokeWidth: 2,
        highlightCircleSize: 3,
      },
      highlightSeriesBackgroundAlpha: 1,
      hideOverlayOnMouseOut: false,
      showRangeSelector: true,
      mousedown: Dygraph.Interaction.dragIsPanInteractionModel.mousedown,
      mousemove: Dygraph.Interaction.dragIsPanInteractionModel.mousemove,
      mouseup: Dygraph.Interaction.dragIsPanInteractionModel.mouseup,
      dateWindow: [
        graph.rows[Math.max(0, graph.rows.length - windowLength - 1)][0],
        graph.rows[graph.rows.length - 1][0],
      ],
    };
    if (graph.type === 'count') {
      options.labels.push('Count');
      options.colors = ['#800'];
    } else if (graph.type === 'list') {
      options.labels.push('Sample Size');
      options.labels.push('Max');
      options.labels.push('99th Percentile');
      options.labels.push('90th Percentile');
      options.labels.push('50th Percentile');
      options.labels.push('Min');
      options.labels.push('Mean');
      options.colors = ['#ccc', '#f00', '#f40', '#f80', '#fc0', '#08f', '#000'];
      options.ylabel = graph.unit;
    } else {
      console.assert(false, 'Unknown type: ' + graph.type);
    }
    var dygraph = new Dygraph(chartDiv, graph.rows, options);
    dygraph.setSelection(graph.rows.length - 1);
  });
  if (!anyGraphs) {
    container.textContent = 'No stats found.';
  }
}

function titleFromName(name) {
  return name.split('-').map(function(word) {
    return /_/.test(word) ? word : word[0].toUpperCase() + word.slice(1);
  }).join(' ');
}

function createElement(className, parent, tagName) {
  tagName = tagName || 'div'
  var div = document.createElement(tagName);
  if (className) {
    div.classList.add(className);
  }
  parent.appendChild(div);
  return div;
}

window.addEventListener('load', main);
})();
