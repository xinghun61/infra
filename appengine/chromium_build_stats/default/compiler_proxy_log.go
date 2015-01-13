// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

// compiler_proxy_log.go provides /compiler_proxy_log endpoints.

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"html/template"
	"net/http"
	"path"
	"sort"
	"strings"
	"time"

	"appengine"

	"github.com/golang/oauth2/google"

	"chromegomalog"
	"compilerproxylog"
)

var (
	compilerProxyLogIndexTempl = template.Must(template.New("compiler_proxy_index").Parse(`
<html>
<head>
 <title>{{.Path}}</title>
</head>
<body>
<h1><a href="/file/{{.Path}}">{{.Path}}</a></h1>
<table>
<tr><th>Filename <td>{{.CompilerProxyLog.Filename}}
<tr><th>Created <td>{{.CompilerProxyLog.Created}}
<tr><th>Machine <td>{{.CompilerProxyLog.Machine}}
<tr><th>GomaRevision <td>{{.CompilerProxyLog.GomaRevision}}
<tr><th>GomaVersion <td>{{.CompilerProxyLog.GomaVersion}}
<tr><th>GomaFlags <td><pre>{{.CompilerProxyLog.GomaFlags}}</pre>
<tr><th>GomaLimits <td>{{.CompilerProxyLog.GomaLimits}}
<tr><th>CrashDump <td>{{.CompilerProxyLog.CrashDump}}
<tr><th>Stats <td><pre>{{.CompilerProxyLog.Stats}}</pre>
<tr><th>Duration <td>{{.CompilerProxyLog.Duration}}
<tr><th>Tasks <td>{{.NumTasks}}
<tr><th>TasksPerSec <td>{{.TasksPerSec}}
</table>

{{range $mode, $bcm := .ByCompileMode}}
<h2>{{$mode}}: # of tasks: {{$bcm.NumTasks}}</h2>
<table>
 <tr><th colspan=2>replices
 {{range $bcm.Resps}}
 <tr><th>{{.Response}}<td>{{.Num}}
 {{end}}
 <tr><th colspan=2>duration
 <tr><th>average <td>{{$bcm.Average}}
 <tr><th>Max     <td>{{$bcm.Max}}
 {{range $bcm.P}}
  <tr><th>{{.P}} <td>{{.D}}
 {{end}}
 <tr><th>Min     <td>{{$bcm.Min}}
 <tr><th colspan=2>log tasks
 {{range $i, $t := $bcm.Tasks}}
  <tr><td>{{$i}} Task:{{$t.ID}}<td>{{$t.Duration}}
   <td>{{$t.Desc}}
   <td>{{$t.Response}}
 {{end}}
</table>
{{end}}

<h2>Duration per num active tasks</h2>
<table>
<tr><th># of tasks <th>duration
{{range $i, $d := .DurationDistribution}}
 <tr><td>{{$i}} <td>{{$d}}
{{end}}
</table>
</body>
</html>
`))
)

func init() {
	http.Handle("/compiler_proxy_log/", http.StripPrefix("/compiler_proxy_log/", http.HandlerFunc(compilerProxyLogHandler)))
}

// compilerProxyLogHandler handles /<path> for compiler_proxy.INFO log file in gs://chrome-goma-log/<path>
func compilerProxyLogHandler(w http.ResponseWriter, req *http.Request) {
	ctx := appengine.NewContext(req)

	// TODO(ukai): should we set access control like /file?

	config := google.NewAppEngineConfig(ctx, []string{
		"https://www.googleapis.com/auth/devstorage.read_only",
	})
	client := &http.Client{Transport: config.NewTransport()}

	basename := path.Base(req.URL.Path)
	if !strings.HasPrefix(basename, "compiler_proxy.") {
		ctx.Errorf("wrong path is requested: %q", req.URL.Path)
		http.Error(w, "unexpected filename", http.StatusBadRequest)
		return
	}
	logPath := req.URL.Path

	cpl, err := compilerProxyLogFetch(client, logPath)
	if err != nil {
		ctx.Errorf("failed to fetch %s: %v", logPath, err)
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	err = compilerProxyLogSummary(w, logPath, cpl)
	if err != nil {
		ctx.Errorf("failed to output %v", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func compilerProxyLogFetch(client *http.Client, logPath string) (*compilerproxylog.CompilerProxyLog, error) {
	resp, err := chromegomalog.Fetch(client, logPath)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	const bufsize = 512 * 1024
	rd, err := gzip.NewReader(bufio.NewReaderSize(resp.Body, bufsize))
	if err != nil {
		return nil, err
	}
	cpl, err := compilerproxylog.Parse(logPath, rd)
	return cpl, nil
}

type byCompileMode struct {
	Tasks    []*compilerproxylog.TaskLog
	NumTasks int
	Resps    []struct {
		Response string
		Num      int
	}
	Average time.Duration
	Max     time.Duration
	P       []struct {
		P int
		D time.Duration
	}
	Min time.Duration
}

func compilerProxyLogSummary(w http.ResponseWriter, logPath string, cpl *compilerproxylog.CompilerProxyLog) error {
	data := struct {
		Path             string
		CompilerProxyLog *compilerproxylog.CompilerProxyLog
		Tasks            []*compilerproxylog.TaskLog
		NumTasks         int
		TasksPerSec      float64

		ByCompileMode map[compilerproxylog.CompileMode]byCompileMode

		DurationDistribution []time.Duration
	}{
		Path:             logPath,
		CompilerProxyLog: cpl,
		Tasks:            cpl.TaskLogs(),
		ByCompileMode:    make(map[compilerproxylog.CompileMode]byCompileMode),
	}
	data.NumTasks = len(data.Tasks)
	data.TasksPerSec = float64(data.NumTasks) / cpl.Duration().Seconds()
	var duration time.Duration
	for _, t := range data.Tasks {
		duration += t.Duration()
	}
	tasksByCompileMode := compilerproxylog.ClassifyByCompileMode(data.Tasks)
	for m, tasks := range tasksByCompileMode {
		mode := compilerproxylog.CompileMode(m)
		sort.Sort(sort.Reverse(compilerproxylog.ByDuration{TaskLogs: tasks}))
		bcm := byCompileMode{
			Tasks:    tasks,
			NumTasks: len(tasks),
		}
		if len(tasks) == 0 {
			data.ByCompileMode[mode] = bcm
			continue
		}
		if len(bcm.Tasks) > 10 {
			bcm.Tasks = bcm.Tasks[:10]
		}
		tr := compilerproxylog.ClassifyByResponse(tasks)
		var resps []string
		for r := range tr {
			resps = append(resps, r)
		}
		sort.Strings(resps)
		for _, r := range resps {
			bcm.Resps = append(bcm.Resps, struct {
				Response string
				Num      int
			}{
				Response: r,
				Num:      len(tr[r]),
			})
		}
		var duration time.Duration
		for _, t := range tasks {
			duration += t.Duration()
		}
		bcm.Average = duration / time.Duration(len(tasks))
		bcm.Max = tasks[0].Duration()
		for _, p := range []int{98, 91, 75, 50, 25, 9, 2} {
			bcm.P = append(bcm.P, struct {
				P int
				D time.Duration
			}{
				P: p,
				D: tasks[int(float64(len(tasks)*(100-p))/100.0)].Duration(),
			})
		}
		bcm.Min = tasks[len(tasks)-1].Duration()
		data.ByCompileMode[mode] = bcm
	}
	data.DurationDistribution = compilerproxylog.DurationDistribution(cpl.Created, data.Tasks)

	var buf bytes.Buffer
	err := compilerProxyLogIndexTempl.Execute(&buf, data)
	if err != nil {
		return err
	}
	w.Header().Set("Content-Type", "text/html")
	_, err = w.Write(buf.Bytes())
	return err
}
