google.load('visualization', '1.0', {'packages':['corechart']});
google.setOnLoadCallback(draw_charts);

function draw_charts() {
  $.getJSON("./all_monthly_stats.json", function(data) {
    var all_commit_data = [['Month', 'Total Commits', 'Total TBR',
        'TBR no LGTM', 'No Review URL',
        'Blank TBRs']].concat(data['all_stats_by_month']);
    var ratio_data = [['Month', 'Suspicious/Total Commits']].concat(
        data['suspicious_to_total_ratio_by_month']);
    var line_charts = [
      ['Commits per Month', all_commit_data, 
          ['#0B486B', '#3B8686', '#79BD9A', '#A8DBA8', '#CFF09E'], 
          'commits_chart'],
      ['Ratio of "Suspicious" Commits to Commits per Month', ratio_data,
          ['#594F4F'], 'ratio_chart'],
    ];
    for (var i = 0; i < line_charts.length; i++) {
      chart_data = line_charts[i];
      draw_line_chart(chart_data[0], chart_data[1], chart_data[2], 
                      chart_data[3]);
    }
  });
}

function congregate_series(headers, all_series) {
  var all_data = [headers];
  for (var data_item = 0; data_item < all_series[0].length; data_item++) {
    var data_point = [all_series[0][data_item][0]];  // date
    for (var series = 0; series < all_series.length; series++) {
      data_point = data_point.concat(all_series[series][data_item][1]);
    }      
    all_data = all_data.concat([data_point]);
  }
  return all_data;
}

function draw_line_chart(chart_title, data, color, element_id) {
  var data = google.visualization.arrayToDataTable(data, false);
  var options = {
    colors: color,
    fontName: 'Quattrocento Sans',
    hAxis: {
      title: 'Month',
      showTextEvery: 5,
    },
    legend: { 
      position: 'right',
      alignment: 'center',
    },
    title: chart_title,
    titleTextStyle: {
      fontSize: 20,
    },
    vAxis: {
      title: 'Commits',
    }
  };
  var chart = new google.visualization.LineChart(
    document.getElementById(element_id));

  chart.draw(data, options);
}

$(window).resize(function() {
  draw_charts();
});