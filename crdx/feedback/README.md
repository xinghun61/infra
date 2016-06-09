# CRDX Feedback Button

## Usage

Include the following script on your site and set the target URL like so:

```html
<script>
  (function(i,s,o,g,r,a,m){i['CrDXObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','https://storage.googleapis.com/crdx-feedback.appspot.com/feedback.js','crdx');

  crdx('setFeedbackButtonLink', 'https://bugs.chromium.org/p/chromium/issues/entry?labels=Infra-DX');
</script>
```

That’s it!

## Development

To make changes to the button, modify `feedback.js`. Once you have made
local changes, preview those changes by loading `file:///path/to/test-page.html`
in your local browser.

## Deployment

To deploy a new version of the button, run the `deploy.sh` script. It uploads
gzipped versions of both the js and the icon to the default Google Storage
bucket of the crdx-feedback Cloud Project. You must have access to that
project in order to upload to the bucket.

Once a new version has been uploaded, it will take up to an hour to fully
roll out based on client-side caching.

