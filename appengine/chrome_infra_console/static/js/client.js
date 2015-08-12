function init(){
  gapi.auth.setToken(null);
  var apisToLoad;
  apisToLoad = 1;
  gapi.client.load('ui', 'v1', loadProjects,'/_ah/api');
}

function loadProjects() {
  console.log("loadProject");
  gapi.client.ui.get_projects().execute(function(resp) {
    document.querySelector('project-dropdown').spin = true;
    var list = [];
    if(resp.configs != null){
      for(var i=0; i< resp.configs.length; i++){
        list.push(resp.configs[i].id);
      };
    };
    list.sort();
    document.querySelector('project-dropdown').projectList = list;
    document.querySelector('project-dropdown').spin = false;
  });
}

function getGraphs(requestData) {
  document.querySelector('console-home').spin = true; 
  gapi.client.ui.get_graphs(requestData).execute(function(resp) {
    var graphs = [];
    if(resp.timeseries != undefined) {
      for(var i = 0 ; i < resp.timeseries.length; i++){
        var metric = resp.timeseries[i].metric;
        var x_axis = ["x"];
        var y_axis = [metric];
        for(var p = 0; p < resp.timeseries[i].points.length; p++){
          var point = resp.timeseries[i].points[p];
          x_axis.push(point.time);
          y_axis.push(point.value);
        };
        var points = [x_axis,y_axis];
        var graph = {};
        graph["draw"] = {columsData: points, labelText: metric};
        graph["fields"] = resp.timeseries[i].fields;
        graphs.push(graph);
      };
    };
    var graphs_packet = {};
    project_id = requestData.project_id; 
    graphs_packet[project_id] = graphs; 
    document.querySelector('console-home').graphs = graphs_packet;
    document.querySelector('console-home').projectChanged();
    document.querySelector('console-home').spin = false; 
    document.querySelector('console-home').projectName = resp.project_name; 
  });

}
  
