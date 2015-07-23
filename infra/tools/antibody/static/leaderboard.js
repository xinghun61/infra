$(document).ready(function(){
  
  $(document).stylesheets[3].disabled = true;

  $('#change_css').onclick=function(){
    if ($(document).stylesheets[3].disabled) {
      $(document).stylesheets[3].disabled = false;
      $(document).stylesheets[2].disabled = true;
    } else {
      $(document).stylesheets[3].disabled = true;
      $(document).stylesheets[2].disabled = false;
    }
  };
});
