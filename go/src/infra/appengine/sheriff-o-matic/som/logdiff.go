package som

import (
	"fmt"
	"html/template"
	"net/http"
	"net/url"
	"strconv"

	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/aryann/difflib"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	"bytes"
	"compress/zlib"
	"encoding/json"
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/common/logging"
	"regexp"
)

const (
	productionAnalyticsID = "UA-55762617-1"
	logDiffTemplate       = `<!DOCTYPE html>

<title>Log Diff</title>

<script src="../../../../bower_components/webcomponentsjs/webcomponents-lite.min.js"></script>
<link rel="import" href="../../../../elements/som-log-diff/som-log-diff.html">

<style>
table {
  font-family: arial, sans-serif;
  border-collapse: collapse;
  width: 100%;
}

td, th {
  border: 1px solid #dddddd;
  text-align:left;
  padding: 8px;
}
</style>

<body>
  <table>
    <tr>
      <th>Master</th>
      <th>Builder</th>
      <th><a href="{{.url1}}">Most Recent Failing Log</a></th>
      <th><a href="{{.url2}}">Last Passing Log</a></th>
    </tr>
    <tr>
      <td>{{.master}}</td>
      <td>{{.builder}}</td>
      <td>{{.buildNum1}}</td>
      <td>{{.buildNum2}}</td>
    </tr>
  </table>
  <som-log-diff master="{{.master}}" builder="{{.builder}}" build-num1="{{.buildNum1}}" build-num2="{{.buildNum2}}"></som-log-diff>
</body>

<script>
{{if not .IsDevAppServer}}
  (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','https://www.google-analytics.com/analytics.js','ga');

  ga('create', '{{.AnalyticsID}}', 'auto');
  ga('send', 'pageview');
{{end}}
</script>`
)

var (
	timestampRE = regexp.MustCompile("\\[[0-9]:[0-9][0-9]:[0-9][0-9]\\]")
	diffSize    = metric.NewInt("sheriff_o_matic/analyzer/diff_size", "diff size over time", nil, field.String("diffsize"))
)

// LogDiff is the entity that will be stored in datastore.
type LogDiff struct {
	// Diffs is the log diff object that will be used to construct the logdiff page.
	Diffs []byte `gae:",noindex"`
	// Master is the master name of these logs.
	Master string
	// Builder is the builder name of these logs.
	Builder string
	// BuildNum1 is the build number of the first log to be diffed.
	BuildNum1 int64
	// BuildNum2 is the build number of the second log to be diffed.
	BuildNum2 int64
	// ID is for GAE purpose
	ID string `gae:"$id"`
	// Complete is recording completeness
	Complete bool
}

// LogDiffJSONHandler will write log diff JSON as an API.
func LogDiffJSONHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params
	master := p.ByName("master")
	builder := p.ByName("builder")
	lo1, err := strconv.Atoi(p.ByName("buildNum1"))
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	lo2, err := strconv.Atoi(p.ByName("buildNum2"))
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	buildNum1 := int64(lo1)
	buildNum2 := int64(lo2)
	var diffs []*LogDiff
	q := datastore.NewQuery("LogDiff")
	q = q.Limit(1)
	q = q.Eq("Master", master).Eq("Builder", builder).Eq("BuildNum1", buildNum1).Eq("BuildNum2", buildNum2)
	err = datastore.GetAll(c, q, &diffs)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error retrieving diffs from datastore: %v", err))
		return
	}
	if len(diffs) <= 0 {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("Can't find specified logdiff"))
		return
	}

	if !diffs[0].Complete {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("Diff file in progress"))
		return
	}
	data := diffs[0].Diffs
	buffer := bytes.NewBuffer(data)
	reader, err := zlib.NewReader(buffer)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error decompressing logdiff: %v", err))
		return
	}
	tmp := new(bytes.Buffer)
	tmp.ReadFrom(reader)
	reader.Close()

	w.Header().Set("Content-Type", "application/json")
	w.Write(tmp.Bytes())
}

// GetLogDiffHandler is showing inline logdiff in a separate page.
func GetLogDiffHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params
	rawURL := p.ByName("master")
	builder := p.ByName("builder")
	lo1, err := strconv.Atoi(p.ByName("buildNum1"))
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	lo2, err := strconv.Atoi(p.ByName("buildNum2"))
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	buildNum1 := int64(lo1)
	buildNum2 := int64(lo2)
	url1 := fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s/logs/stdio/text", rawURL, builder, buildNum1, "steps")
	url2 := fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s/logs/stdio/text", rawURL, builder, buildNum2, "steps")
	diffPage := template.Must(template.New("log-index").Parse(logDiffTemplate))

	data := map[string]interface{}{
		"master":         rawURL,
		"builder":        builder,
		"buildNum1":      buildNum1,
		"buildNum2":      buildNum2,
		"IsDevAppServer": info.IsDevAppServer(c),
		"AnalyticsID":    productionAnalyticsID,
		"url1":           url1,
		"url2":           url2,
	}
	err = diffPage.Execute(w, data)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error rendering log-index: %v", err))
		return
	}
}

// LogdiffWorker is performing diff and storing on tasks in logdiff queue.
func LogdiffWorker(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	master := r.FormValue("master")
	builder := r.FormValue("builder")
	lastPass := r.FormValue("lastPass")
	lastFail := r.FormValue("lastFail")
	masURL, err := url.Parse(master)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error parsing url: %v", err))
		return
	}
	Master := &messages.MasterLocation{URL: *masURL}
	lo1, err := strconv.Atoi(lastFail)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	lo2, err := strconv.Atoi(lastPass)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	buildNum1 := int64(lo1)
	buildNum2 := int64(lo2)
	reader := client.GetReader(c)
	if reader == nil {
		transport, err := auth.GetRPCTransport(c, auth.AsSelf)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error getting transport: %v", err))
			return
		}
		c = urlfetch.Set(c, transport)

		miloReader, err := client.NewMiloReader(c, "")
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error creating milo client: %v", err))
			return
		}
		memcachingReader := client.NewMemcacheReader(miloReader)
		c = client.WithReader(c, memcachingReader)
	}
	//TODO(renjietang): make goroutine to fetch logs concurrently
	res1, err := client.StdioForStep(c, Master, builder, "steps", buildNum1)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error fetching log: %v", err))
		return
	}
	res2, err := client.StdioForStep(c, Master, builder, "steps", buildNum2)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error fetching log: %v", err))
		return
	}

	for i, line := range res1 {
		res1[i] = timestampRE.ReplaceAllString(line, "")
	}
	for i, line := range res2 {
		res2[i] = timestampRE.ReplaceAllString(line, "")
	}
	diffs := difflib.Diff(res1, res2)
	diffSize.Set(c, int64(len(diffs)), "diffSize")
	data, err := json.Marshal(diffs)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error marshaling JSON for logdiff: %v", err))
		return
	}

	var buffer bytes.Buffer
	writer := zlib.NewWriter(&buffer)
	writer.Write(data)
	writer.Close()

	diff := &LogDiff{ID: r.FormValue("ID")}
	datastore.Get(c, diff)
	diff.Diffs = buffer.Bytes()
	diff.Complete = true
	err = datastore.Put(c, diff)
	if err != nil {
		logging.Errorf(c, "error putting data into datastore: %v", err)
	}
}
