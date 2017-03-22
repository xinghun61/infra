function addIncidents(pageData) {
  renderIncidents(pageData['ChopsServices']);
  renderIncidents(pageData['NonSLAServices']);
}

function renderIncidents(services){
  for(var i=0; i < services.length; i++) {
    var service = services[i];
    var service_name = service['Name'];
    for (var j=0; j < service['Incidents'].length; j++) {
      var incident = service['Incidents'][j];
      var td_id = service_name + '-' + incident['StartTime'];
      var dateCell = document.getElementById(td_id);
      var img = document.createElement('img');
      img.className='light';

      if (incident['Severity']==1) {
        img.src = '../static/red.png';
      }
      if (incident['Severity']==2) {
        img.src = '../static/yellow.png';
      }
      dateCell.appendChild(img);
    }
  }
}
