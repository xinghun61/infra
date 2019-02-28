package client

import (
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"

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

func (bc *buildbucketClient) LatestBuilds(ctx context.Context, builderIDs []*bbpb.BuilderID) ([]*bbpb.Build, error) {
	logging.Infof(ctx, "getting latest builds from buildbucket")

	// Change this to a BatchRequest? Would need to change the signature of this func.

	reqs := []*bbpb.BatchRequest_Request{}

	for _, builderID := range builderIDs {
		reqs = append(reqs, &bbpb.BatchRequest_Request{
			Request: &bbpb.BatchRequest_Request_SearchBuilds{
				SearchBuilds: &bbpb.SearchBuildsRequest{
					Predicate: &bbpb.BuildPredicate{
						Builder: builderID,
					},
					Fields: &field_mask.FieldMask{
						// Request build steps be included since they aren't by default.
						Paths: []string{"builds.*.steps"},
					},
				}}})
	}
	req := &bbpb.BatchRequest{
		Requests: reqs,
	}

	batchResp, err := bc.BuildBucket.Batch(ctx, req)
	if err != nil {
		logging.Errorf(ctx, "error getting most recent builds for %q: %v", builderIDs, err)
		return nil, err
	}

	ret := []*bbpb.Build{}
	for _, resp := range batchResp.Responses {
		searchResp := resp.GetSearchBuilds()
		ret = append(ret, searchResp.Builds...)
		logging.Infof(ctx, "got %d builds", len(searchResp.Builds))
	}
	// TODO: paginate, get all in memory before returning.
	return ret, nil
}
