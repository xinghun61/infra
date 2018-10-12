package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// HandleLegacy serves the /legacy endpoint.
func (h *State) HandleLegacy(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	name := ctx.Params.ByName("name")

	vf, ok := h.legacyMap[name]
	if !ok {
		http.Error(ctx.Writer, "not found", http.StatusNotFound)
		return
	}

	item := memcache.NewItem(ctx.Context, name)
	if err := memcache.Get(ctx.Context, item); err != nil {
		logging.Warningf(ctx.Context, "%q not in the cache", name)
		val, err := vf(ctx, name)
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		fmt.Fprint(ctx.Writer, val)
		return
	}
	fmt.Fprint(ctx.Writer, string(item.Value()))
}

const (
	trooperCal   = "google.com_3aov6uidfjscpj2hrpsd8i4e7o@group.calendar.google.com"
	matchSummary = "CCI-Trooper:"
)

type trooperJSON struct {
	Primary   string   `json:"primary"`
	Secondary []string `json:"secondary"`
	UnixTS    int64    `json:"updated_unix_timestamp"`
}

func (h *State) legacyTrooper(ctx *router.Context, file string) (string, error) {
	updated := clock.Now(ctx.Context)
	oc, err := h.legacyCalendar.TrooperOncall(ctx, trooperCal, matchSummary, updated)
	if err != nil && status.Code(err) != codes.NotFound {
		return "", err
	}
	switch file {
	case "trooper.js":
		str := "None"
		if len(oc) > 0 {
			str = oc[0]
			if len(oc) > 1 {
				str += ", secondary: " + strings.Join(oc[1:], ", ")
			}
		}
		return "document.Write('" + str + "');", nil
	case "current_trooper.json":
		var buf bytes.Buffer
		primary := "None"
		var secondary []string
		if len(oc) > 0 {
			primary = oc[0]
			if len(oc) > 1 {
				secondary = oc[1:]
			}
		}
		enc := json.NewEncoder(&buf)
		if err := enc.Encode(&trooperJSON{
			Primary:   primary,
			Secondary: secondary,
			UnixTS:    updated.Unix(),
		}); err != nil {
			return "", err
		}
		return buf.String(), nil
	case "current_trooper.txt":
		if len(oc) == 0 {
			return "None", nil
		}
		return strings.Join(oc, ","), nil
	default:
		return "", status.Errorf(codes.InvalidArgument, "legacyTrooper only handles `trooper.js` and `current_trooper.txt`")
	}
}
