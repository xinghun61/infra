# CRDX Feedback Button

## Usage

Include the following script on your site and set the target URL like so:

```html
<script>
  (function(i,s,o,g,r,a,m){i['CrDXObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','https://storage.googleapis.com/crdx-feedback.appspot.com/feedback.js','crdx');

  crdx('setFeedbackButtonLink', 'https://bugs.chromium.org');
  crdx('setFeedbackButtonBackgroundColor', 'green'); // Any valid CSS value is ok.
</script>
```

That’s it!
