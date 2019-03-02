package client

import (
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/sync/parallel"
	"google.golang.org/genproto/protobuf/field_mask"
)

type buildbucketClient struct {
	BuildBucket bbpb.BuildsClient
}

func (bc *buildbucketClient) Build(ctx context.Context, id int64) (*bbpb.Build, error) {
	logging.Infof(ctx, "getting build from buildbucket")

	req := &bbpb.GetBuildRequest{
		Id: id,
	}
	build, err := bc.BuildBucket.GetBuild(ctx, req)
	if err != nil {
		logging.Errorf(ctx, "error getting build ID %d: %v", id, err)
		return nil, err
	}

	logging.Infof(ctx, "got build: %+v", *build)

	return build, nil
}

const maxConcurrentBuilders = 20
const pageSize = 50

func (bc *buildbucketClient) LatestBuilds(ctx context.Context, builderIDs []*bbpb.BuilderID) ([]*bbpb.Build, error) {
	ret := []*bbpb.Build{}

	type r struct {
		builderID *bbpb.BuilderID
		builds    []*bbpb.Build
		err       error
	}

	workers := len(builderIDs)
	if workers > maxConcurrentBuilders {
		workers = maxConcurrentBuilders
	}
	logging.Infof(ctx, "getting latest builds from buildbucket for %d builders, using %d pool workers", len(builderIDs), workers)

	c := make(chan r, len(builderIDs))

	err := parallel.WorkPool(workers, func(workC chan<- func() error) {
		for _, builderID := range builderIDs {
			builderID := builderID
			workC <- func() error {
				out := r{
					builderID: builderID,
				}
				req := &bbpb.SearchBuildsRequest{
					Predicate: &bbpb.BuildPredicate{
						Builder: builderID,
						// TODO: expand this logic to handle in-process builds.
						Status: bbpb.Status_ENDED_MASK,
					},
					Fields: &field_mask.FieldMask{
						// Request fields to be included since they aren't by default.
						Paths: []string{
							"builds.*.status",
							"builds.*.steps.*.name",
							"builds.*.steps.*.status",
							"builds.*.builder",
							"builds.*.number",
							"builds.*.start_time",
						},
					},
					PageSize: pageSize,
				}

				resp, err := bc.BuildBucket.SearchBuilds(ctx, req)
				if err != nil {
					logging.Errorf(ctx, "error getting most recent builds for %+v: %v", builderID, err)
					out.err = err
				}
				if resp != nil {
					logging.Debugf(ctx, "got %d builds for %+v", len(resp.Builds), builderID)
					out.builds = resp.Builds
				}

				c <- out
				return nil
			}
		}
	})

	if err != nil {
		logging.Errorf(ctx, "Error from worker pool: %v", err)
	}

	logging.Debugf(ctx, "about to read worker output from c.")
	i := 0
	for range builderIDs {
		r := <-c
		i++
		logging.Debugf(ctx, "%d builds for %+v (%d/%d)", len(r.builds), r.builderID, i, len(builderIDs))
		err = r.err
		if err != nil {
			logging.Errorf(ctx, "error getting builds for %+v: %+v", r.builderID, r.err)
		}
		ret = append(ret, r.builds...)
	}

	if len(ret) == 0 {
		return ret, err
	}

	return ret, nil
}
