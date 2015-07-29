function init(){
  gapi.auth.setToken(null);
  var apisToLoad;
  apisToLoad = 1;
  gapi.client.load('ui', 'v1', loadProjects,'/_ah/api');
}

function loadProjects() {
  gapi.client.ui.get_projects().execute(function(resp) {
    document.querySelector('project-dropdown').spin = true;
    var list = [];
    if(resp.configs != null){
      for(var i=0; i< resp.configs.length; i++){
        list.push(resp.configs[i].id);
      };
    };
    document.querySelector('project-dropdown').projectList = list;
    document.querySelector('project-dropdown').spin = false;
  });
}

  
