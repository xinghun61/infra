package handlers

import (
	"bytes"
	"infra/appengine/rotang/pkg/datastore"
	"infra/appengine/rotang/pkg/jsoncfg"
	"infra/appengine/rotang/pkg/rotang"
	"io"
	"net/http"
	"strings"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

const (
	jsonFile = ".json"
)

// HandleUpload handles legacy JSON configurations.
func HandleUpload(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if ctx.Request.Method == "GET" {
		templates.MustRender(ctx.Context, ctx.Writer, "pages/upload.html", templates.Args{})
		return
	}
	mr, err := ctx.Request.MultipartReader()
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		logging.Errorf(ctx.Context, "ctx.RequestMultipartReader failed: %v", err)
		return
	}

	var ds rotang.ConfigStorer = datastore.New()

	for {
		part, err := mr.NextPart()
		if err != nil {
			if err == io.EOF {
				break
			}
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		var buf bytes.Buffer
		if !strings.HasSuffix(part.FileName(), jsonFile) {
			logging.Errorf(ctx.Context, "File: %q not a json file", part.FileName())
			continue
		}
		if _, err := io.Copy(&buf, part); err != nil {
			logging.Errorf(ctx.Context, "File: %q containing: %q failed to Copy: %v", part.FileName(), buf, err)
			continue
		}
		rotaCfg, err := jsoncfg.BuildConfigurationFromJSON(buf.Bytes())
		if err != nil {
			logging.Errorf(ctx.Context, "File: %q failed to parse: %v", part.FileName(), err, "</br>")
			http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
			return
		}
		if err := ds.StoreRotaConfig(ctx.Context, rotaCfg); err != nil {
			logging.Errorf(ctx.Context, "File: %q failed to store: %v", part.FileName(), err)
			continue
		}
	}
}
