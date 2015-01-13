// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

// ninja_log.go provides /ninja_log endpoints.

import (
	"bufio"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"path"
	"sort"
	"strings"

	"appengine"

	"github.com/golang/oauth2/google"

	"chromegomalog"
	"ninjalog"
	"ninjalog/traceviewer"
)

type outputFunc func(http.ResponseWriter, string, *ninjalog.NinjaLog) error

var (
	outputs = map[string]outputFunc{
		"lastbuild":     outputFunc(lastBuild),
		"table":         outputFunc(table),
		"metadata.json": outputFunc(metadataJSON),
		"trace.json":    outputFunc(traceJSON),
		"trace.html":    outputFunc(traceHTML),
	}

	// chromegomalog.URL(path) won't be accessible by user.
	indexTmpl = template.Must(template.New("index").Parse(`
<html>
<head>
 <title>{{.Path}}</title>
</head>
<body>
<h1><a href="/file/{{.Path}}">{{.Path}}</a></h1>
<ul>
 <li><a href="{{.Filename}}/lastbuild">.ninja_log</a>
 <li><a href="{{.Filename}}/table">.ninja_log in table format</a>
 <li><a href="{{.Filename}}/metadata.json">metadata.json</a>
 <li><a href="{{.Filename}}/trace.html">trace viewer</a> [<a href="{{.Filename}}/trace.json">trace.json</a>]
</ul>
</body>
</html>
`))

	tableTmpl = template.Must(template.New("table").Parse(`
<html>
<head>
 <title>{{.Filename}}</title>
</head>
<body>
<h1>{{.Filename}}</h1>
Platform: {{.Metadata.Platform}}
Cmdline: {{.Metadata.Cmdline}}
Exit:{{.Metadata.Exit}}
<hr />
<table border=1>
<tr>
 <th>n
 <th>duration
 <th>start
 <th>end
 <th>restat
 <th>output
</tr>
{{range $i, $step := .Steps}}
<tr>
 <td><a name="{{$i}}" href="#{{$i}}">{{$i}}</a>
 <td>{{$step.Duration}}
 <td>{{$step.Start}}
 <td>{{$step.End}}
 <td>{{if gt $step.Restat 0}}{{$step.Restat}}{{end}}
 <td>{{$step.Out}}
</tr>
{{end}}
</table>
</html>
`))

	traceViewerTmpl = traceviewer.Must(traceviewer.Parse("tmpl/trace-viewer.html"))
)

func init() {
	http.Handle("/ninja_log/", http.StripPrefix("/ninja_log/", http.HandlerFunc(ninjaLogHandler)))
}

// ninjaLogHandler handles /<path>/<format> for ninja_log file in gs://chrome-goma-log/<path>
func ninjaLogHandler(w http.ResponseWriter, req *http.Request) {
	ctx := appengine.NewContext(req)

	// should we set access control like /file?

	config := google.NewAppEngineConfig(ctx, []string{
		"https://www.googleapis.com/auth/devstorage.read_only",
	})
	client := &http.Client{Transport: config.NewTransport()}

	logPath, outFunc, err := ninjalogPath(req.URL.Path)
	if err != nil {
		ctx.Errorf("failed to parse request path: %s: %v", req.URL.Path, err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	njl, _, err := ninjalogFetch(client, logPath)
	if err != nil {
		ctx.Errorf("failed to fetch %s: %v", logPath, err)
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	err = outFunc(w, logPath, njl)
	if err != nil {
		ctx.Errorf("failed to output %v", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func ninjalogPath(reqPath string) (string, outputFunc, error) {
	basename := path.Base(reqPath)
	for format, f := range outputs {
		if basename == format {
			logPath := path.Dir(reqPath)
			return logPath, f, nil
		}
	}
	if !strings.HasPrefix(basename, "ninja_log.") {
		return "", nil, fmt.Errorf("unexpected path %s", reqPath)
	}
	return strings.TrimSuffix(reqPath, "/"), outputFunc(indexPage), nil
}

func ninjalogFetch(client *http.Client, logPath string) (*ninjalog.NinjaLog, http.Header, error) {
	resp, err := chromegomalog.Fetch(client, logPath)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	const bufsize = 512 * 1024
	rd, err := gzip.NewReader(bufio.NewReaderSize(resp.Body, bufsize))
	if err != nil {
		return nil, nil, err
	}
	nl, err := ninjalog.Parse(logPath, rd)
	return nl, resp.Header, nil
}

func indexPage(w http.ResponseWriter, logPath string, njl *ninjalog.NinjaLog) error {
	w.Header().Set("Content-Type", "text/html")
	w.WriteHeader(http.StatusOK)
	data := struct {
		Path     string
		Filename string
	}{
		Path:     logPath,
		Filename: path.Base(njl.Filename),
	}
	return indexTmpl.Execute(w, data)
}

func lastBuild(w http.ResponseWriter, logPath string, njl *ninjalog.NinjaLog) error {
	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(http.StatusOK)
	return ninjalog.Dump(w, njl.Steps)
}

func table(w http.ResponseWriter, logPath string, njl *ninjalog.NinjaLog) error {
	w.Header().Set("Content-Type", "text/html")
	w.WriteHeader(http.StatusOK)
	sort.Sort(sort.Reverse(ninjalog.ByDuration{Steps: njl.Steps}))
	return tableTmpl.Execute(w, njl)
}

func metadataJSON(w http.ResponseWriter, logPath string, njl *ninjalog.NinjaLog) error {
	js, err := json.Marshal(njl.Metadata)
	if err != nil {
		return err
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, err = w.Write(js)
	return err
}

func traceJSON(w http.ResponseWriter, logPath string, njl *ninjalog.NinjaLog) error {
	steps := ninjalog.Dedup(njl.Steps)
	flow := ninjalog.Flow(steps)
	traces := ninjalog.ToTraces(flow, 1)
	js, err := json.Marshal(traces)
	if err != nil {
		return err
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, err = w.Write(js)
	return err
}

func traceHTML(w http.ResponseWriter, logPath string, njl *ninjalog.NinjaLog) error {
	steps := ninjalog.Dedup(njl.Steps)
	flow := ninjalog.Flow(steps)
	traces := ninjalog.ToTraces(flow, 1)
	b, err := traceViewerTmpl.HTML(logPath, traces)
	if err != nil {
		return err
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, err = w.Write(b)
	return err
}
