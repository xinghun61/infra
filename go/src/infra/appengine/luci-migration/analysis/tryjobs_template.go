// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package analysis

import (
	"html/template"
	"time"

	"infra/appengine/luci-migration/common"
)

var pdtLoc *time.Location

func init() {
	var err error
	pdtLoc, err = time.LoadLocation("US/Pacific")
	if err != nil {
		panic(err)
	}
}

// tmplDetails is an HTML template that consumes a comparison struct and
// produces the HTML report of analysis, which will be displayed on a builder
// page.
var tmplDetails = template.Must(template.New("").Funcs(template.FuncMap{
	"abs": func(x time.Duration) time.Duration {
		if x < 0 {
			x = -x
		}
		return x
	},
	"durationString": common.DurationString,
	"timeString": func(t time.Time) string {
		// in practice t is in [now-week, now] range, so
		// day of the week is precise enough and short.
		return t.In(pdtLoc).Format("Mon 15:04:05 MST")
	},
}).Parse(`
{{define "buildResults"}}
  {{- range $index, $b := . -}}
    {{- if gt $index 0}}, {{end -}}
<a href="{{$b.URL}}">{{$b.Status}}</a>
  {{- end }}
at {{.MostRecentlyCompleted | timeString }}.
{{end}}

{{define "groups"}}
<ol>
  {{range .}}
  <li>
    <div>Build group for
      {{if .KeyURL -}}
        <a href="{{.KeyURL}}">{{.KeyURL}}</a>
      {{- else -}}
        {{.Key}}
      {{- end}}
    </div>
    <div>Buildbot: {{template "buildResults" .Buildbot}}</div>
    <div>LUCI: {{template "buildResults" .LUCI}}</div>
  </li>
  {{end}}
</ol>
{{end}}

<ul>
  <li>Status reason: {{.StatusReason}}</li>
  {{- if gt .MinBuildAge 0 -}}
  {{- end -}}
  </li>
  <li>
    <strong>Correctness</strong>:
    analyzed {{.TotalGroups}} build groups,
    rejected {{.RejectedCorrectnessGroups}} of them:
    {{len .FalseFailures}} have false failures,
    {{len .FalseSuccesses}} have false successes
  </li>
  <li>
    <strong>Speed</strong>:
  {{if lt .Correctness 0.9 }}
    cannot be estimated because correctness is low
  {{else}}
    analyzed {{.AvgTimeDeltaGroups}} build groups:
    on average LUCI is
    {{if gt .AvgTimeDelta 0 -}}
    <span style="color:red">{{.AvgTimeDelta | durationString}} slower</span>
    {{- else -}}
    <span style="color:green">{{abs .AvgTimeDelta | durationString}} faster</span>
    {{- end}}
    than Buildbot, according to build run durations.
  {{end}}
  </li>
  <li>Considered builds at most {{.MinBuildAge | durationString}} old</li>
</ul>

{{if .FalseFailures}}
<h3>False failures on LUCI</h3>
{{template "groups" .FalseFailures}}
{{end}}

{{if .FalseSuccesses}}
<h3>False successes on LUCI</h3>
{{template "groups" .FalseSuccesses}}
{{end}}

{{/* add slow builds */}}
`))
