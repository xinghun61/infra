var prev_width = $(window).width();
var inflection_resolution = 991;
$(window).resize(function() {
  var curr_width = $(window).width();
  if (prev_width < inflection_resolution && curr_width > inflection_resolution) {
    $('table').bootstrapTable();
  }
  prev_width = curr_width;
});