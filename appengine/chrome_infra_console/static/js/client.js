function init(){
  gapi.auth.setToken(null);
  var apisToLoad;
  apisToLoad = 1;
  gapi.client.load('ui', 'v1', loadProjects,'/_ah/api');
}

function loadProjects() {
  gapi.client.ui.get_projects().execute(function(resp) {
    var list = [];
    if(resp.projects != null){
      for(var i=0; i< resp.projects.length; i++){
        list.push({name: resp.projects[i].name, id: resp.projects[i].id});
      };
    };
    document.querySelector('project-dropdown').projectList = list;
  });
}

  
