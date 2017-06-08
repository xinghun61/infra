package analysis

import (
	"html/template"
	"time"
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
}).Parse(`
{{define "buildResults"}}
  {{- range $index, $b := . -}}
    {{- if gt $index 0}}, {{end -}}
<a href="{{$b.Url}}">{{$b.Result}}</a>
  {{- end -}}
{{end}}

{{define "groups"}}
<ol>
  {{range .}}
  <li>
    <p>Build set for
      {{if .KeyURL -}}
        <a href="{{.KeyURL}}">{{.Key}}</a>
      {{- else -}}
        {{.Key}}
      {{- end}}
    <p>
    <p>Buildbot: {{template "buildResults" .Buildbot}}</p>
    <p>LUCI: {{template "buildResults" .LUCI}}</p>
  </li>
  {{end}}
</ol>
{{end}}

<ul>
  <li>Status: {{.Status}}</li>
  <li>Status reason: {{.StatusReason}}</li>
  {{- if not .MinBuildCreationDate.IsZero -}}
  <li>Considered builds since {{.MinBuildCreationDate}}</li>
  {{- end -}}
  </li>
  <li>
    <strong>Correctness</strong>:
    analyzed {{.TotalGroups}} build groups,
    rejected {{.UntrustworthyGroups}} of them:
    {{len .FalseFailures}} have false failures,
    {{len .FalseSuccesses}} have false successes
  </li>
  <li>
    <strong>Speed</strong>:
    analyzed {{.TotalGroups}} build groups:
    on average LUCI is
    {{if gt .AvgTimeDelta 0 -}}
    <span style="color:red">{{.AvgTimeDelta}} slower</span>
    {{- else -}}
    <span style="color:green">{{abs .AvgTimeDelta}} faster</span>
    {{- end}}
    than Buildbot
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
