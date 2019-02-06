package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const jsonHeader = "application/json"

type jsonMember struct {
	Name  string
	Email string
	TZ    string
}

type jsonRota struct {
	Cfg     rotang.Configuration
	Members []jsonMember
}

// HandleRotaCreate handles creation of new rotations.
func (h *State) HandleRotaCreate(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if ctx.Request.Method == "POST" {
		var res jsonRota
		if err := json.NewDecoder(ctx.Request.Body).Decode(&res); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		_, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, res.Cfg.Config.Name)
		if status.Code(err) != codes.NotFound {
			if err == nil {
				http.Error(ctx.Writer, "rotation exists", http.StatusInternalServerError)
				return
			}
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		if err := h.createRota(ctx, &res); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		return
	}

	var genBuf bytes.Buffer
	if err := json.NewEncoder(&genBuf).Encode(h.generators.List()); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	var modBuf bytes.Buffer
	if err := json.NewEncoder(&modBuf).Encode(h.generators.ListModifiers()); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	templates.MustRender(ctx.Context, ctx.Writer, "pages/rotacreate.html", templates.Args{"Generators": genBuf.String(), "Modifiers": modBuf.String()})
}

func (h *State) validateConfig(ctx *router.Context, jr *jsonRota) error {
	members, err := convertMembers(jr.Members)
	if err != nil {
		return err
	}

	if err := h.updateMembers(ctx.Context, members); err != nil {
		return err
	}

	if !adminOrOwner(ctx, &jr.Cfg) {
		return status.Errorf(codes.PermissionDenied, "not admin or owner")
	}

	// To not create empty Owners entries.
	var cleanOwners []string
	for _, o := range jr.Cfg.Config.Owners {
		if o == "" {
			continue
		}
		cleanOwners = append(cleanOwners, o)
	}
	jr.Cfg.Config.Owners = cleanOwners

	if dur, ok := checkShiftDuration(&jr.Cfg); !ok {
		return status.Errorf(codes.InvalidArgument, "shift durations does not add up to 24h,got %v", dur)
	}
	return nil
}

func (h *State) createRota(ctx *router.Context, jr *jsonRota) error {
	if err := h.validateConfig(ctx, jr); err != nil {
		return err
	}

	return h.configStore(ctx.Context).CreateRotaConfig(ctx.Context, &jr.Cfg)
}

func (h *State) modifyRota(ctx *router.Context, cfg *rotang.Configuration, jr *jsonRota) error {
	if err := h.validateConfig(ctx, jr); err != nil {
		return err
	}
	// Want to keep the Enabled state of the config before.
	// Enable/Disable of the configuration is handled elsewhere.
	jr.Cfg.Config.Enabled = cfg.Config.Enabled
	return h.configStore(ctx.Context).UpdateRotaConfig(ctx.Context, &jr.Cfg)
}

// checkShiftDuration checks if the shift durations add up to 24 hours.
func checkShiftDuration(cfg *rotang.Configuration) (time.Duration, bool) {
	var totalDuration time.Duration
	for _, s := range cfg.Config.Shifts.Shifts {
		totalDuration += s.Duration
	}
	if totalDuration == fullDay {
		return totalDuration, true
	}
	return totalDuration, false
}

// convertMembers converts between the jsonMember format to rotang.Member.
// In practice this is just changing the TZ field from string to time.Location.
func convertMembers(jm []jsonMember) ([]rotang.Member, error) {
	var res []rotang.Member
	for _, m := range jm {
		tz, err := time.LoadLocation(m.TZ)
		if err != nil {
			return nil, err
		}
		res = append(res, rotang.Member{
			Name:  m.Name,
			Email: m.Email,
			TZ:    *tz,
		})
	}
	return res, nil
}

// updateMembers adds in members in the member list not already in the pool.
// Members already represented in the pool are updated.
func (h *State) updateMembers(ctx context.Context, members []rotang.Member) error {
	ms := h.memberStore(ctx)
	for _, m := range members {
		_, err := ms.Member(ctx, m.Email)
		switch {
		case err == nil:
			if err := ms.UpdateMember(ctx, &m); err != nil {
				return err
			}
		case status.Code(err) == codes.NotFound:
			if err := ms.CreateMember(ctx, &m); err != nil {
				return err
			}
		default:
			return err
		}
	}
	return nil
}

// HandleRotaModify is used to modify or copy rotation configurations.
func (h *State) HandleRotaModify(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	switch ctx.Request.Method {
	case "GET":
		args, err := h.modifyRotation(ctx)
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		templates.MustRender(ctx.Context, ctx.Writer, "pages/rotamodify.html", args)
		return
	case "POST":
		var res jsonRota
		if err := json.NewDecoder(ctx.Request.Body).Decode(&res); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		rotas, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, res.Cfg.Config.Name)
		if err != nil {
			if status.Code(err) == codes.NotFound {
				if err := h.createRota(ctx, &res); err != nil {
					http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
				}
				return
			}
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		if err := h.modifyRota(ctx, rotas[0], &res); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
	default:
		http.Error(ctx.Writer, "HandleModifyRota handles only GET and POST requests", http.StatusBadRequest)
		return
	}
}
