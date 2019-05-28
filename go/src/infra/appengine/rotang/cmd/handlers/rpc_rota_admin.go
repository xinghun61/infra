package handlers

import (
	"context"
	"regexp"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/rotang"

	apb "infra/appengine/rotang/proto/rotangapi"
)

var emailRE = regexp.MustCompile(`^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,4}$`)

// CreateExternal creates a new External rotation.
func (h *State) CreateExternal(ctx context.Context, req *apb.CreateExternalRequest) (*apb.CreateExternalResponse, error) {
	switch {
	case req.GetName() == "":
		return nil, status.Errorf(codes.InvalidArgument, "rotation name is required")
	case req.GetCalendar() == "":
		return nil, status.Errorf(codes.InvalidArgument, "calendar ID required")
	case req.GetMatch() == "":
		return nil, status.Errorf(codes.InvalidArgument, "match is required")
	case len(req.GetOwnersEmails()) < 1:
		return nil, status.Errorf(codes.InvalidArgument, "owners_emails is required")
	}

	for _, m := range req.GetOwnersEmails() {
		if !emailRE.MatchString(m) {
			return nil, status.Errorf(codes.InvalidArgument, "not a valid e-mail address: %q", m)
		}
	}

	return &apb.CreateExternalResponse{}, h.configStore(ctx).CreateRotaConfig(ctx, &rotang.Configuration{
		Config: rotang.Config{
			Name:          req.GetName(),
			Description:   req.GetDescription(),
			Owners:        req.GetOwnersEmails(),
			External:      true,
			ExternalMatch: req.GetMatch(),
		},
	})
}

// DeleteExternal deletes an external rotation.
func (h *State) DeleteExternal(ctx context.Context, req *apb.DeleteExternalRequest) (*apb.DeleteExternalResponse, error) {
	if req.GetName() == "" {
		return nil, status.Errorf(codes.InvalidArgument, "rotation name is required")
	}

	cfg, err := h.configStore(ctx).RotaConfig(ctx, req.GetName())
	if err != nil {
		return nil, err
	}

	if len(cfg) != 1 {
		return nil, status.Errorf(codes.Internal, "RotaConfig did not return 1 configuration, got: %d", len(cfg))
	}

	if !isOwner(ctx, cfg[0]) {
		return nil, status.Errorf(codes.PermissionDenied, "not an owner of rotation: %q", req.GetName())
	}

	return &apb.DeleteExternalResponse{}, h.configStore(ctx).DeleteRotaConfig(ctx, req.GetName())
}
