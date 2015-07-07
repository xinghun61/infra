$(document).ready(function(){
  $(".username").keypress(function(e){
    if (e.keyCode == 13) {
      var user = $(".username").val();
      $('.tbr').empty();
      get_commits_tbred_to_user(user);
    }
  });

  function get_commits_tbred_to_user(user) {
    $.getJSON("./tbr_by_user.json", function(data) {
      var commits_tbred_to_user = data["by_user"][user];
      if (commits_tbred_to_user === undefined) {
        $('.tbr').append($('<h3>').text(
            `No commits to be reviewed by ${user}`));
      } else {
        gitiles_prefix = data["gitiles_prefix"];
        $('.tbr').append($('<h3>').text(`Commits to be reviewed by ${user}`));
        $('.tbr').append(document.createElement('br'));
        var table = $('<table>').attr('data-toggle', 'table').attr(
          'data-cache', 'false');
        table.append($('<thead>').append($('<tr>').append(
            $('<th>').attr('data-field', 'git_hash label').text('git_hash'),
            $('<th>').attr('data-field', 'rietveld_url label').text(
                'rietveld_url'),
            $('<th>').attr('data-field', 'request_timestamp').text(
                'request_timestamp')
          )));
        var tbody = $('<tbody>');
        for (var i = 0; i < commits_tbred_to_user.length; i++) {
          data_item = commits_tbred_to_user[i];
          tbody.append($('<tr>').addClass('data_item').append(
              $('<td>').addClass('git_hash hyperlink').append(
                $('<a>').attr('href', `${gitiles_prefix}${data_item[0]}`).text(
                  `${data_item[0]}`)),
              $('<td>').addClass('rietveld_url hyperlink').append(
                $('<a>').attr('href', `${data_item[1]}`).text(
                  `${data_item[1]}`)),
              $('<td>').addClass('request_timestamp').text(`${data_item[2]}`)
            ));
        }
        table.append(tbody);
        $('.tbr').append(table);
      }
    });
  }
});
