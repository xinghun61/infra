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
      console.log(data);
      console.log('hello');
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
            $('<th>').attr('data-field', 'subject label').text('Git Commit Subject'),
            $('<th>').attr('data-field', 'rietveld_url label').text(
                'Review URL'),
            $('<th>').attr('data-field', 'request_timestamp').text(
                'Request Timestamp')
          )));
        var tbody = $('<tbody>');
        for (var i = 0; i < commits_tbred_to_user.length; i++) {
          data_item = commits_tbred_to_user[i];
          console.log(data_item);
          tbody.append($('<tr>').addClass('data_item').append(
              $('<td>').addClass('subject hyperlink').append(
                $('<a>').attr('href', `${gitiles_prefix}${data_item[3]}`).text(
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
