(function($) {
  var toggler_num = 1;
  function makeToggler(name) {
    toggler_num++;
    var togglers = $('#settings ul').first();
    var label = $('<label/>');
    label.text(name);
    var checkbox = $('<input type="checkbox" />');
    var cookiename = 'chromecal-ticked-' + name;
    var column = $('#rotations tr td:nth-child(' + toggler_num + ')')
            .add($('#rotations tr th:nth-child(' + toggler_num + ')'));
     if ($.cookie(cookiename) === 'f') {
       column.hide();
     } else {
       checkbox.prop('checked', 'true');
       column.show();
     }
     checkbox.change(function() {
       var cookieval = $(this).is(':checked') ? 't' : 'f';
       $.cookie(cookiename, cookieval, { expires: 9999 });
       column.toggle();
     });
     label.prepend(checkbox);
     label.append('<br/>');
     var li = $('<li/>');
     li.append(label);
     togglers.append(li);
  }

  function makeCell(kind, text) {
    return $('<' + kind + ' class="centered"/>').text(text);
  }

  function parseJson(json) {
    // console.log('Got this from data.txt: [' + json + ']');

    var json_obj;
    try {
      json_obj = $.parseJSON(json);
    } catch (err) {
      console.error('Couldn\'t parse [' + json + ']');
      throw err;
    }
    var rotations = json_obj['rotations'];
    var calendar = json_obj['calendar'];
    var table = $('#rotations');

    var row = $('<tr/>');
    row.append(makeCell('th', 'Date'));

    for (var r of rotations) {
      row.append(makeCell('th', r));
    }

    table.append(row);

    for (var c of calendar) {
      row = $('<tr/>');
      row.append(makeCell('th', c['date']));
      for (var p of c['participants']) {
        row.append(makeCell('td', p.join(' / ')));
      }
      table.append(row);
    }

    for (var r of rotations) {
      makeToggler(r);
    }
  }

  function reHighlight(match_string, color) {
    if (! /\S/.test(match_string)) {
      console.error('reHighlight() called with no match_string');
    } else if (! /\S/.test(color)) {
      console.error('reHighlight() called with no color');
    } else {
      $('#rotations td').css('background-color', '');
      var to_highlight = $('#rotations td').filter(function() {
        return $(this).text().indexOf(match_string) > -1;
      });
      to_highlight.css('background-color', color);
    }
  }

  function initHighlights() {
    $('#settings input').each(function() {
      var cookiename = 'chromecal-' + $(this).attr('id');
      var cookieval = $.cookie(cookiename);
      $(this).val(cookieval);
    });

    $('#settings input').change(function() {
      var cookiename = 'chromecal-' + $(this).attr('id');
      var cookieval = $(this).val();
      $.cookie(cookiename, cookieval, { expires: 9999 });
      reHighlight($('#highlight_string').val(), $('#highlight_color').val());
     });

    reHighlight($('#highlight_string').val(), $('#highlight_color').val());
  }

  $(document).ready(function() {
    $.get('/p/chromium/all_rotations.js', function(json) {
      parseJson(json);
      initHighlights();
    }, 'text')
    .fail(function(jqxhr, text_status, error) {
      console.log(jqxhr.responseText);
      var err = text_status + ', ' + error + ', code=' + jqxhr.status;
      console.error('error: [' + err + ']');
    });

    $('#settings_button').click(function() {
      $('#settings').toggle();
    });
  });
})(jQuery);
