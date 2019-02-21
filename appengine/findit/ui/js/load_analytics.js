/*
Copyright 2018 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.

This is a copy of the Google Analytics snippet obtained from
https://www.google.com/analytics/.
*/

(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','//www.google-analytics.com/analytics.js','ga');

ga('create', 'UA-118440270-1', 'auto');
// Use the URL hostname & path so that parameters are removed automatically.
ga('set', 'hostname', document.location.hostname);
ga('set', 'page', document.location.pathname);
ga('send', 'pageview');
