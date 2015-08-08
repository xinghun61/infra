$(document).ready(function(e){
    $('.search-panel .dropdown-menu').find('a').click(function(e) {
    e.preventDefault();
    var param = $(this).attr("href").replace("#","");
    var concept = $(this).text();
    $('.search-panel span#search_concept').text(concept);
    $('.input-group #search_param').val(param);
  });
});


$(document).ready(function(){
  $(".type_menu").on("click", "li", function(event){
    update_table();
  });

  document.getElementById("search_btn").addEventListener('click', function(){
    update_table();
  });

  $(".username").keypress(function(e){
    if (e.keyCode === 13) { update_table(); }
  });

  function update_table() {
    var user = $(".username").val();
    if (user !== "") {
      var search_param = $(".input-group #search_param").val();
      $('.tbr').empty();
      get_commits_by_user(user, search_param);
    }
  }

  function get_commits_by_user(user, search_param) {
    $.getJSON("./search_by_user.json", function(data) {
      var commits_by_user = data["by_user"][user];
      if (commits_by_user === undefined) {
        $('.tbr').append($('<h3>').text(
            `No commits to be reviewed by ${user}`));
      } else {
        gitiles_prefix = data["gitiles_prefix"];
        var help_text = ""
        switch(search_param) {
          case "tbr":
            commits_by_user = commits_by_user[search_param];
            help_text = "Commits TBR'ed to";
            break;
          case "author":
            commits_by_user = commits_by_user[search_param];
            help_text = "Commits authored by";
            break;
          case "all":
          default:
            help_text = "All commits for";
            commits_by_user = commits_by_user["tbr"].concat(
                              commits_by_user["author"])
            commits_by_user.sort(function(a, b) {
              return new Date(a[2].replace(" ", "T")+"Z") - new Date(
                  b[2].replace(" ", "T")+"Z");
            });
        }
        $('.tbr').append($('<h3>').text(`${help_text} ${user}`));
        $('.tbr').append(document.createElement('br'));
        var table = $('<table>').attr('data-toggle', 'table').attr(
          'data-cache', 'false');
        table.append($('<thead>').append($('<tr>').append(
            $('<th>').attr('data-field', 'request_timestamp').text(
                'Commit Timestamp (UTC)'),
            $('<th>').attr('data-field', 'rietveld_url label').text(
                'Code Review'),
            $('<th>').attr('data-field', 'subject label').text('Git Commit Hash'),
            $('<th>').attr('data-field', 'type').text(
                'Type')
          )));
        var tbody = $('<tbody>');
        for (var i = 0; i < commits_by_user.length; i++) {
          // [subject, url, timestamp, git_hash, { 'TBR' | 'Author'} ]
          data_item = commits_by_user[i];
          tbody.append($('<tr>').addClass('data_item').append(
              $('<td>').addClass('commit_timestamp').text(`${data_item[2]}`),
              $('<td>').addClass('rietveld_url hyperlink').append(
                $('<a>').attr('href', `${data_item[1]}`).attr(
                  'target', '_blank').text(`${data_item[0]}`)),
              $('<td>').addClass('subject hyperlink').append(
                $('<a>').attr('href', `${gitiles_prefix}${data_item[3]}`).attr(
                  'target', '_blank').text(`${data_item[3]}`)),
              $('<td>').addClass('type').text(`${data_item[4]}`)
            ));
        }
        table.append(tbody);
        $('.tbr').append(table);
        $("table").bootstrapTable();
      }
    });
  }
});