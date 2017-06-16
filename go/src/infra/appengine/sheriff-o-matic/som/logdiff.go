package som

import (
	"fmt"
	"html/template"
	"net/http"
	"net/url"

	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/aryann/difflib"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	"encoding/json"
)

// LogDiffHandler will write log diff JSON as an API
func LogDiffHandler(ctx *router.Context) {
	c, w, _ := ctx.Context, ctx.Writer, ctx.Params
	masURL, _ := url.Parse("chromium.webkit")
	Master := &messages.MasterLocation{URL: *masURL}
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
	res1, err1 := client.StdioForStep(c, Master, "WebKit Mac10.11 (dbg)", "steps", 9098)
	res2, err2 := client.StdioForStep(c, Master, "WebKit Mac10.11 (dbg)", "steps", 9099)
	if err1 != nil {
		logging.Errorf(c, "error getting gatekeeper rules: %v", err1)
	}
	if err2 != nil {
		logging.Errorf(c, "error getting gatekeeper rules: %v", err2)
	}
	diffs := difflib.Diff(res1, res2)
	data, _ := json.Marshal(diffs)
	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

// GetLogDiffHandler is showing inline logdiff in a separate page
func GetLogDiffHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	diffPage := template.Must(template.ParseFiles("./log-index.html"))
	err := diffPage.Execute(w, nil)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
}
