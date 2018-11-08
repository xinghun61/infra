package handlers

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/appengine"
)

// baseURL left as a var to make testing a bit easier.
var baseURL = "https://datastore.googleapis.com/v1/projects"

const (
	bucketPfx  = "rota-ng-"
	bucketSfx  = "-backup"
	export     = ":export"
	timeFormat = "20060102-15:04:05"
)

type exportReq struct {
	ProjectID    string   `json:"projectId"`
	URLPrefix    string   `json:"outputUrlPrefix"`
	EntityFilter []string `json:"entityFilter"`
}

// JobBackup handles scheduled backups of the datastore.
func (h *State) JobBackup(ctx *router.Context) {
	logging.Infof(ctx.Context, "Was here")
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	appCTX := appengine.NewContext(ctx.Request)
	logging.Infof(ctx.Context, "ID: %q", h.projectID(appCTX))

	client, err := h.backupCred(appCTX)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	now := clock.Now(ctx.Context)

	var jsonReq bytes.Buffer
	enc := json.NewEncoder(&jsonReq)
	if err := enc.Encode(&exportReq{
		ProjectID: h.projectID(appCTX),
		// gs://rota-ng-staging-backup/staging-20181106-01:43:43
		URLPrefix: "gs://" + bucketPfx + h.prodENV + bucketSfx + "/" + h.prodENV + "-" + now.Format(timeFormat),
	}); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	req, err := http.NewRequest("POST", baseURL+"/"+h.projectID(appCTX)+export, &jsonReq)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if resp.StatusCode != http.StatusOK {
		var body bytes.Buffer
		if _, err := io.Copy(&body, resp.Body); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		logging.Warningf(ctx.Context, "Backup response: %v", body.String())
		http.Error(ctx.Writer, resp.Status, http.StatusInternalServerError)
	}
}
