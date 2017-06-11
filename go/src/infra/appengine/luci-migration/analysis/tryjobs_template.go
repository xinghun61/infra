package analysis

import (
	"html/template"
	"time"

	"infra/appengine/luci-migration/common"
)

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
}).Parse(`
{{define "buildResults"}}
  {{- range $index, $b := . -}}
    {{- if gt $index 0}}, {{end -}}
<a href="{{$b.Url}}">{{$b.Result}}</a>
  {{- end }}
{{.Age | durationString}} ago.
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
  <li>Status: {{.Status}}</li>
  <li>Status reason: {{.StatusReason}}</li>
  {{- if gt .MinBuildAge 0 -}}
  <li>Considered builds at most {{.MinBuildAge | durationString}} old</li>
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
    analyzed {{.AvgTimeDeltaGroups}} build groups:
    on average LUCI is
    {{if gt .AvgTimeDelta 0 -}}
    <span style="color:red">{{.AvgTimeDelta | durationString}} slower</span>
    {{- else -}}
    <span style="color:green">{{abs .AvgTimeDelta | durationString}} faster</span>
    {{- end}}
    than Buildbot, according to build run durations.
  </li>
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
