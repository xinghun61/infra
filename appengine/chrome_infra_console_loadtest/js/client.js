var clientID="1053480191491-1u50p49gsi961g91urgftep4tr8k93d0.apps.googleusercontent.com";

function init(){
  gapi.auth.setToken(null);
  var apisToLoad;
  apisToLoad = 1;
  var loadCallback = function() {
    signin(false, userAuthed);    
  };
  gapi.client.load('ui', 'v1', loadCallback,'/_ah/api');
}

function userAuthed() {
  console.log("userAuthed");
  gapi.client.ui.ui.get().execute(function(resp) {
    console.log("get!");

    var numPoints = Math.floor(resp.time/ resp.freq);
    var timeSize = 4; //Estimated
    var metricValueSize = 4; //Estimated
    var singleSize = ((timeSize + metricValueSize)*numPoints)/1000000;
    var fileSize = singleSize;
    for(var i=0; i < resp.params.length; i++){
       fileSize = fileSize*((resp.params[i].values).length);
    }
    fileSize = fileSize.toString();

    document.querySelector('field-slider').currentFreq = resp.freq;
    document.querySelector('field-slider').currentRange = resp.time/86400;
    document.querySelector('add-field').fieldsPresent = resp.params;
    document.querySelector('#fileSize').innerText = fileSize ;
  });
}

function setPara(requestData) {
  gapi.client.ui.ui.set(requestData).execute(function(resp) {
    console.log("Set works!");
  });
}

function signin(mode, authorizeCallback) {
  gapi.auth.setToken(null);
  gapi.auth.authorize({client_id: clientID,
  scope: "email", immediate: mode},
  authorizeCallback);
}
  
