package mock

//go:generate mockgen -destination=milo_mock.go go.chromium.org/luci/milo/api/proto BuildbotClient,BuildInfoClient
