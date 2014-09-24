// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package chromiumbuildstats implements chromium-build-stats.appspot.com services.
package chromiumbuildstats

import (
	"fmt"
	"net/http"
	"path"
	"strings"
)

const (
	topHTML = `
<html>
<head><title>chromium-build-stats</title></head>
<body>
<h1>chromium-build-stats</h1>
<form action="/">
<label for="gsuri">gs URI:</label><input type="text" name="gsuri" />
<input type="submit" value="submit"><input type="reset">
</form>

<hr />
See <a href="https://docs.google.com/a/chromium.org/document/d/16TdPTIIZbtAarXZIMJdiT9CePG5WYCrdxm5u9UuHXNY/edit?pli=1#heading=h.xgjl2srtytjt">design doc</a>
</body>
</html>
`
)

func init() {
	http.HandleFunc("/", handler)

}

func handler(w http.ResponseWriter, req *http.Request) {
	gsuri := req.FormValue("gsuri")
	if gsuri != "" {
		if strings.HasPrefix(gsuri, "gs://chrome-goma-log") {
			logPath := strings.TrimPrefix(gsuri, "gs://chrome-goma-log")
			basename := path.Base(gsuri)
			switch {
			case strings.HasPrefix(basename, "ninja_log."):
				http.Redirect(w, req, "/ninja_log"+logPath, http.StatusSeeOther)
				return
			case strings.HasPrefix(basename, "compiler_proxy."):
				http.Redirect(w, req, "/compiler_proxy_log"+logPath, http.StatusSeeOther)
				return
			}
		}
		http.NotFound(w, req)
		return
	}
	w.Header().Set("Content-Type", "text/html")
	fmt.Fprintf(w, topHTML)
}
