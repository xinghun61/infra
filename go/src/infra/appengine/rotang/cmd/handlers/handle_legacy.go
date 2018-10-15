package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/rotang"
	"net/http"
	"strings"
	"time"

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
		return "document.write('" + str + "');", nil
	case "current_trooper.json":
		primary := "None"
		var secondary []string
		if len(oc) > 0 {
			primary = oc[0]
			if len(oc) > 1 {
				secondary = oc[1:]
			}
		}

		var buf bytes.Buffer
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

var fileToRota = map[string][2]string{
	"sheriff.js": {"Build Sheriff", ""},
	// "sheriff_webkit.js":              "",
	// "sheriff_memory.js":              "",
	"sheriff_cros_mtv.js":          {"Chrome OS Build Sheriff", ""},
	"sheriff_cros_nonmtv.js":       {"Chrome OS Build Sheriff - Other", "Chrome OS Build Sheriff"},
	"sheriff_perf.js":              {"Chromium Perf Regression Sheriff Rotation", ""},
	"sheriff_cr_cros_gardeners.js": {"Chrome on ChromeOS Gardening", ""},
	"sheriff_gpu.js":               {"Chrome GPU Pixel Wrangling", ""},
	"sheriff_angle.js":             {"The ANGLE Wrangle", ""},
	"sheriff_android.js":           {"Chrome on Android Build Sheriff", ""},
	"sheriff_ios.js":               {"Chrome iOS Build Sheriff", ""},
	"sheriff_v8.js":                {"V8 Sheriff", ""},
	"sheriff_perfbot.js":           {"Chromium Perf Bot Sheriff Rotation", ""},

	"sheriff.json": {"Build Sheriff", ""},
	// "sheriff_webkit.json":            "",
	// "sheriff_memory.json":            "",
	"sheriff_cros_mtv.json":          {"Chrome OS Build Sheriff", ""},
	"sheriff_cros_nonmtv.json":       {"Chrome OS Build Sheriff - Other", "Chrome OS Build Sheriff"},
	"sheriff_perf.json":              {"Chromium Perf Regression Sheriff Rotation", ""},
	"sheriff_cr_cros_gardeners.json": {"Chrome on ChromeOS Gardening", ""},
	"sheriff_gpu.json":               {"Chrome GPU Pixel Wrangling", ""},
	"sheriff_angle.json":             {"The ANGLE Wrangle", ""},
	"sheriff_android.json":           {"Chrome on Android Build Sheriff", ""},
	"sheriff_ios.json":               {"Chrome iOS Build Sheriff", ""},
	"sheriff_v8.json":                {"V8 Sheriff", ""},
	"sheriff_perfbot.json":           {"Chromium Perf Bot Sheriff Rotation", ""},
	//"all_rotations.js":               "",
	//"all_rotations.js":               "",
}

const week = 7 * 24 * time.Hour

type sheriffJSON struct {
	UnixTS int64    `json:"updated_unix_timestamp"`
	Emails []string `json:"emails"`
}

// legacySheriff produces the legacy cron created sherriff oncall files.
func (h *State) legacySheriff(ctx *router.Context, file string) (string, error) {
	rota, ok := fileToRota[file]
	if !ok {
		return "", status.Errorf(codes.InvalidArgument, "file: %q not handled by legacySheriff", file)
	}
	r, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rota[0])
	if err != nil {
		return "", err
	}
	if len(r) != 1 {
		return "", status.Errorf(codes.Internal, "RotaConfig did not return 1 configuration")
	}
	cfg := r[0]
	// As a workaround to handle split shifts some users create multiple configurations with different
	// calendars but the same Event Name. The new service use the rota name as a key in the datastore.
	if rota[1] != "" {
		cfg.Config.Name = rota[1]
	}

	updated := clock.Now(ctx.Context)
	events, err := h.legacyCalendar.Events(ctx, cfg, updated.Add(-week), updated.Add(week))
	if err != nil {
		return "", err
	}

	var entry rotang.ShiftEntry
	for _, e := range events {
		if (updated.After(e.StartTime) || updated.Equal(e.StartTime)) &&
			updated.Before(e.EndTime) {
			entry = e
		}
	}

	sp := strings.Split(file, ".")
	if len(sp) != 2 {
		return "", status.Errorf(codes.InvalidArgument, "filename in wrong format")
	}

	switch sp[1] {
	case "js":
		var oc []string
		for _, o := range entry.OnCall {
			oc = append(oc, strings.Split(o.Email, "@")[0])
		}
		str := "None"
		if len(oc) > 0 {
			str = strings.Join(oc, ", ")
		}
		return "document.write('" + str + "');", nil
	case "json":
		oc := make([]string, 0)
		for _, o := range entry.OnCall {
			oc = append(oc, o.Email)
		}
		var buf bytes.Buffer
		enc := json.NewEncoder(&buf)
		if err := enc.Encode(&sheriffJSON{
			UnixTS: updated.Unix(),
			Emails: oc,
		}); err != nil {
			return "", err
		}
		return buf.String(), nil

	default:
		return "", status.Errorf(codes.InvalidArgument, "filename in wrong format")
	}
}
