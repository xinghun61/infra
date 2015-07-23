google.load('visualization', '1.0', {'packages':['corechart']});
google.setOnLoadCallback(draw_charts);

function draw_charts() {
  $.getJSON("./all_monthly_stats.json", function(data) {
    monthly_breakdown = data['monthly_breakdown'];
    var colors = [['#594F4F'], ['#547980', '#45ADA8', '#9DE0AD', '#E5FCC2']];
    var ratio_data = congregate_series(
      ['Month', 'Suspicious/Total Commits'],
      [monthly_breakdown['suspicious_to_total_ratio']]
    );
    var all_commit_data = congregate_series(
      ['Month', 'Total Commits', 'TBR no LGTM', 'No Review URL', 'Blank TBRs'],
      [
        monthly_breakdown['total_commits'], 
        monthly_breakdown['tbr_no_lgtm'], 
        monthly_breakdown['no_review_url'], 
        monthly_breakdown['blank_tbrs'],
      ]
    );
    var line_charts = [
      ['Ratio of "Suspicious" Commits to Commits per Month', ratio_data,
          'ratio_chart'],
      ['Commits per Month', all_commit_data, 'commits_chart'],
    ];
    for (var i = 0; i < line_charts.length; i++) {
      chart_data = line_charts[i];
      draw_line_chart(chart_data[0], chart_data[1], chart_data[2],
          colors[i]);
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

function draw_line_chart(chart_title, data, element_id, color) {
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

function resize () {
  draw_charts();
}

window.onresize = resize;