package handlers

import (
	"bytes"
	"io"
	"net/http"
	"strings"

	"infra/appengine/rotang/pkg/datastore"
	"infra/appengine/rotang/pkg/jsoncfg"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	jsonFile = ".json"
)

// HandleUpload handles legacy JSON configurations.
func (h *State) HandleUpload(ctx *router.Context) {
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

	ds, err := datastore.New(ctx.Context)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

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
		rotaCfg, members, err := jsoncfg.BuildConfigurationFromJSON(buf.Bytes())
		if err != nil {
			logging.Errorf(ctx.Context, "File: %q failed to parse: %v", part.FileName(), err, "</br>")
			http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
			return
		}
		for _, m := range members {
			if err := ds.CreateMember(ctx.Context, &m); err != nil && status.Code(err) != codes.AlreadyExists {
				http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
				return
			}
		}
		if err := ds.CreateRotaConfig(ctx.Context, rotaCfg); err != nil {
			logging.Errorf(ctx.Context, "File: %q failed to store: %v", part.FileName(), err)
			continue
		}
	}
}
