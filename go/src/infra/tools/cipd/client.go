// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package cipd implements client side of Chrome Infra Package Deployer.

TODO: write more.

Binary package file format (in free form representation):
  <binary package> := <zipped data>
  <zipped data> := DeterministicZip(<all input files> + <manifest json>)
  <manifest json> := File{
    name: ".cipdpkg/manifest.json",
    data: JSON({
      "FormatVersion": "1",
      "PackageName": <name of the package>
    }),
  }
  DeterministicZip = zip archive with deterministic ordering of files and stripped timestamps

Main package data (<zipped data> above) is deterministic, meaning its content
depends only on inputs used to built it (byte to byte): contents and names of
all files added to the package (plus 'executable' file mode bit) and a package
name (and all other data in the manifest).

Binary package data MUST NOT depend on a timestamp, hostname of machine that
built it, revision of the source code it was built from, etc. All that
information will be distributed as a separate metadata packet associated with
the package when it gets uploaded to the server.

TODO: expand more when there's server-side package data model (labels
and stuff).
*/
package cipd

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/luci/luci-go/common/logging"

	"infra/tools/cipd/common"
	"infra/tools/cipd/local"
)

// PackageACLChangeAction defines a flavor of PackageACLChange.
type PackageACLChangeAction string

const (
	// GrantRole is used in PackageACLChange to request a role to be granted.
	GrantRole PackageACLChangeAction = "GRANT"
	// RevokeRole is used in PackageACLChange to request a role to be revoked.
	RevokeRole PackageACLChangeAction = "REVOKE"

	// CASFinalizationTimeout is how long to wait for CAS service to finalize the upload.
	CASFinalizationTimeout = 1 * time.Minute
	// SetRefTimeout is how long to wait for an instance to be processed when setting a ref.
	SetRefTimeout = 1 * time.Minute
	// TagAttachTimeout is how long to wait for an instance to be processed when attaching tags.
	TagAttachTimeout = 1 * time.Minute

	// UserAgent is HTTP user agent string for CIPD client.
	UserAgent = "cipd 1.0"

	// ServiceURL is URL of a backend to connect to by default.
	ServiceURL = "https://chrome-infra-packages.appspot.com"
)

var (
	// ErrFinalizationTimeout is returned if CAS service can not finalize upload fast enough.
	ErrFinalizationTimeout = errors.New("Timeout while waiting for CAS service to finalize the upload")
	// ErrBadUpload is returned when a package file is uploaded, but servers asks us to upload it again.
	ErrBadUpload = errors.New("Package file is uploaded, but servers asks us to upload it again")
	// ErrBadUploadSession is returned by UploadToCAS if provided UploadSession is not valid.
	ErrBadUploadSession = errors.New("UploadURL must be set if UploadSessionID is used")
	// ErrUploadSessionDied is returned by UploadToCAS if upload session suddenly disappeared.
	ErrUploadSessionDied = errors.New("Upload session is unexpectedly missing")
	// ErrNoUploadSessionID is returned by UploadToCAS if server didn't provide upload session ID.
	ErrNoUploadSessionID = errors.New("Server didn't provide upload session ID")
	// ErrSetRefTimeout is returned when service refuses to move a ref for a long time.
	ErrSetRefTimeout = errors.New("Timeout while moving a ref")
	// ErrAttachTagsTimeout is returned when service refuses to accept tags for a long time.
	ErrAttachTagsTimeout = errors.New("Timeout while attaching tags")
	// ErrDownloadError is returned by FetchInstance on download errors.
	ErrDownloadError = errors.New("Failed to download the package file after multiple attempts")
	// ErrUploadError is returned by RegisterInstance and UploadToCAS on upload errors.
	ErrUploadError = errors.New("Failed to upload the package file after multiple attempts")
	// ErrAccessDenined is returned by calls talking to backend on 401 or 403 HTTP errors.
	ErrAccessDenined = errors.New("Access denied (not authenticated or not enough permissions)")
	// ErrBackendInaccessible is returned by calls talking to backed if it doesn't response.
	ErrBackendInaccessible = errors.New("Request to the backend failed after multiple attempts")
	// ErrEnsurePackagesFailed is returned by EnsurePackages if something is not right.
	ErrEnsurePackagesFailed = errors.New("Failed to update packages, see the log")
)

// PackageACL is per package path per role access control list that is a part of
// larger overall ACL: ACL for package "a/b/c" is a union of PackageACLs for "a"
// "a/b" and "a/b/c".
type PackageACL struct {
	// PackagePath is a package subpath this ACL is defined for.
	PackagePath string
	// Role is a role that listed users have, e.g. 'READER', 'WRITER', ...
	Role string
	// Principals list users and groups granted the role.
	Principals []string
	// ModifiedBy specifies who modified the list the last time.
	ModifiedBy string
	// ModifiedTs is a timestamp when the list was modified the last time.
	ModifiedTs time.Time
}

// PackageACLChange is a mutation to some package ACL.
type PackageACLChange struct {
	// Action defines what action to perform: GrantRole or RevokeRole.
	Action PackageACLChangeAction
	// Role to grant or revoke to a user or group.
	Role string
	// Principal is a user or a group to grant or revoke a role for.
	Principal string
}

// UploadSession describes open CAS upload session.
type UploadSession struct {
	// ID identifies upload session in the backend.
	ID string
	// URL is where to upload the data to.
	URL string
}

// Client provides high-level CIPD client interface.
type Client interface {
	// FetchACL returns a list of PackageACL objects (parent paths first) that
	// together define the access control list for the given package subpath.
	FetchACL(packagePath string) ([]PackageACL, error)

	// ModifyACL applies a set of PackageACLChanges to a package path.
	ModifyACL(packagePath string, changes []PackageACLChange) error

	// UploadToCAS uploads package data blob to Content Addressed Store if it is
	// not there already. The data is addressed by SHA1 hash (also known as
	// package's InstanceID). It can be used as a standalone function (if
	// 'session' is nil) or as a part of more high level upload process (in that
	// case upload session can be opened elsewhere and its properties passed here
	// via 'session' argument). Returns nil on successful upload.
	UploadToCAS(sha1 string, data io.ReadSeeker, session *UploadSession) error

	// ResolveVersion converts an instance ID, a tag or a ref into a concrete Pin
	// by contacting the backend.
	ResolveVersion(packageName, version string) (common.Pin, error)

	// RegisterInstance makes the package instance available for clients by
	// uploading it to the storage and registering it in the package repository.
	// 'instance' is a package instance to register.
	RegisterInstance(instance local.PackageInstance) error

	// SetRefWhenReady moves a ref to point to a package instance, retrying on
	// "not yet processed" responses.
	SetRefWhenReady(ref string, pin common.Pin) error

	// AttachTagsWhenReady attaches tags to an instance, retrying on "not yet
	// processed" responses.
	AttachTagsWhenReady(pin common.Pin, tags []string) error

	// FetchInstance downloads package instance file from the repository.
	FetchInstance(pin common.Pin, output io.WriteSeeker) error

	// FetchAndDeployInstance fetches the package instance and deploys it into
	// the site root. It doesn't check whether the instance is already deployed.
	FetchAndDeployInstance(pin common.Pin) error

	// ListPackages returns a list of strings of package names.
	ListPackages(path string, recursive bool) ([]string, error)

	// ProcessEnsureFile parses text file that describes what should be installed
	// by EnsurePackages function. It is a text file where each line has a form:
	// <package name> <desired version>. Whitespaces are ignored. Lines that start
	// with '#' are ignored. Version can be specified as instance ID, tag or ref.
	// Will resolve tags and refs to concrete instance IDs by calling the backend.
	ProcessEnsureFile(r io.Reader) ([]common.Pin, error)

	// EnsurePackages is high-level interface for installation, removal and update
	// of packages inside the installation site root. Given a description of
	// what packages (and versions) should be installed it will do all necessary
	// actions to bring the state of the site root to the desired one.
	EnsurePackages(pins []common.Pin) error
}

// HTTPClientFactory lazily creates http.Client to use for making requests.
type HTTPClientFactory func() (*http.Client, error)

// ClientOptions is passed to NewClient factory function.
type ClientOptions struct {
	// ServiceURL is root URL of the backend service.
	ServiceURL string
	// Root is a site root directory (where packages will be installed). It can
	// be empty string if client is not going to be used to deploy or remove local packages.
	Root string
	// Logger is a logger to use for logs (null-logger by default).
	Logger logging.Logger
	// AuthenticatedClientFactory lazily creates http.Client to use for making RPC requests.
	AuthenticatedClientFactory HTTPClientFactory
	// AnonymousClientFactory lazily creates http.Client to use for making requests to storage.
	AnonymousClientFactory HTTPClientFactory
	// UserAgent is put into User-Agent HTTP header with each request.
	UserAgent string
}

// NewClient initializes CIPD client object.
func NewClient(opts ClientOptions) Client {
	if opts.ServiceURL == "" {
		opts.ServiceURL = ServiceURL
	}
	if opts.Logger == nil {
		opts.Logger = logging.Null()
	}
	if opts.AnonymousClientFactory == nil {
		opts.AnonymousClientFactory = func() (*http.Client, error) { return http.DefaultClient, nil }
	}
	if opts.AuthenticatedClientFactory == nil {
		opts.AuthenticatedClientFactory = opts.AnonymousClientFactory
	}
	if opts.UserAgent == "" {
		opts.UserAgent = UserAgent
	}
	c := &clientImpl{
		ClientOptions: opts,
		clock:         &clockImpl{},
	}
	c.remote = &remoteImpl{c}
	c.storage = &storageImpl{c, uploadChunkSize}
	c.deployer = local.NewDeployer(opts.Root, opts.Logger)
	return c
}

type clientImpl struct {
	ClientOptions

	// clock provides current time and ability to sleep.
	clock clock
	// remote knows how to call backend REST API.
	remote remote
	// storage knows how to upload and download raw binaries using signed URLs.
	storage storage
	// deployer knows how to install packages to local file system.
	deployer local.Deployer

	// authClient is a lazily created http.Client to use for authenticated requests.
	authClient *http.Client
	// anonClient is a lazily created http.Client to use for anonymous requests.
	anonClient *http.Client
}

// doAuthenticatedHTTPRequest is used by remote implementation to make HTTP calls.
func (client *clientImpl) doAuthenticatedHTTPRequest(req *http.Request) (*http.Response, error) {
	if client.authClient == nil {
		var err error
		client.authClient, err = client.AuthenticatedClientFactory()
		if err != nil {
			return nil, err
		}
	}
	return client.authClient.Do(req)
}

// doAnonymousHTTPRequest is used by storage implementation to make HTTP calls.
func (client *clientImpl) doAnonymousHTTPRequest(req *http.Request) (*http.Response, error) {
	if client.anonClient == nil {
		var err error
		client.anonClient, err = client.AnonymousClientFactory()
		if err != nil {
			return nil, err
		}
	}
	return client.anonClient.Do(req)
}

func (client *clientImpl) FetchACL(packagePath string) ([]PackageACL, error) {
	return client.remote.fetchACL(packagePath)
}

func (client *clientImpl) ModifyACL(packagePath string, changes []PackageACLChange) error {
	return client.remote.modifyACL(packagePath, changes)
}

func (client *clientImpl) ListPackages(path string, recursive bool) ([]string, error) {
	pkgs, dirs, err := client.remote.listPackages(path, recursive)
	if err != nil {
		return nil, err
	}

	// Add trailing slash to directories.
	for k, d := range dirs {
		dirs[k] = d + "/"
	}
	// Merge and sort packages and directories.
	allPkgs := append(pkgs, dirs...)
	sort.Strings(allPkgs)
	return allPkgs, nil
}

func (client *clientImpl) UploadToCAS(sha1 string, data io.ReadSeeker, session *UploadSession) error {
	// Open new upload session if an existing is not provided.
	var err error
	if session == nil {
		client.Logger.Infof("cipd: uploading %s: initiating", sha1)
		session, err = client.remote.initiateUpload(sha1)
		if err != nil {
			client.Logger.Warningf("cipd: can't upload %s - %s", sha1, err)
			return err
		}
		if session == nil {
			client.Logger.Infof("cipd: %s is already uploaded", sha1)
			return nil
		}
	} else {
		if session.ID == "" || session.URL == "" {
			return ErrBadUploadSession
		}
	}

	// Upload the file to CAS storage.
	err = client.storage.upload(session.URL, data)
	if err != nil {
		return err
	}

	// Finalize the upload, wait until server verifies and publishes the file.
	started := client.clock.now()
	delay := time.Second
	for {
		published, err := client.remote.finalizeUpload(session.ID)
		if err != nil {
			client.Logger.Warningf("cipd: upload of %s failed: %s", sha1, err)
			return err
		}
		if published {
			client.Logger.Infof("cipd: successfully uploaded %s", sha1)
			return nil
		}
		if client.clock.now().Sub(started) > CASFinalizationTimeout {
			client.Logger.Warningf("cipd: upload of %s failed: timeout", sha1)
			return ErrFinalizationTimeout
		}
		client.Logger.Infof("cipd: uploading - verifying")
		client.clock.sleep(delay)
		if delay < 4*time.Second {
			delay += 500 * time.Millisecond
		}
	}
}

func (client *clientImpl) ResolveVersion(packageName, version string) (common.Pin, error) {
	if err := common.ValidatePackageName(packageName); err != nil {
		return common.Pin{}, err
	}
	// Is it instance ID already? Don't bother calling the backend.
	if common.ValidateInstanceID(version) == nil {
		return common.Pin{PackageName: packageName, InstanceID: version}, nil
	}
	if err := common.ValidateInstanceVersion(version); err != nil {
		return common.Pin{}, err
	}
	client.Logger.Infof("cipd: resolving version %q of %q...", version, packageName)
	return client.remote.resolveVersion(packageName, version)
}

func (client *clientImpl) RegisterInstance(instance local.PackageInstance) error {
	// Attempt to register.
	client.Logger.Infof("cipd: registering %s", instance.Pin())
	result, err := client.remote.registerInstance(instance.Pin())
	if err != nil {
		return err
	}

	// Asked to upload the package file to CAS first?
	if result.uploadSession != nil {
		err = client.UploadToCAS(instance.Pin().InstanceID, instance.DataReader(), result.uploadSession)
		if err != nil {
			return err
		}
		// Try again, now that file is uploaded.
		client.Logger.Infof("cipd: registering %s", instance.Pin())
		result, err = client.remote.registerInstance(instance.Pin())
		if err != nil {
			return err
		}
		if result.uploadSession != nil {
			return ErrBadUpload
		}
	}

	if result.alreadyRegistered {
		client.Logger.Infof(
			"cipd: instance %s is already registered by %s on %s",
			instance.Pin(), result.registeredBy, result.registeredTs)
	} else {
		client.Logger.Infof("cipd: instance %s was successfully registered", instance.Pin())
	}

	return nil
}

func (client *clientImpl) SetRefWhenReady(ref string, pin common.Pin) error {
	if err := common.ValidatePackageRef(ref); err != nil {
		return err
	}
	if err := common.ValidatePin(pin); err != nil {
		return err
	}
	client.Logger.Infof("cipd: setting ref of %q: %q => %q", pin.PackageName, ref, pin.InstanceID)
	deadline := client.clock.now().Add(SetRefTimeout)
	for client.clock.now().Before(deadline) {
		err := client.remote.setRef(ref, pin)
		if err == nil {
			return nil
		}
		if _, ok := err.(*pendingProcessingError); ok {
			client.Logger.Warningf("cipd: package instance is not ready yet - %s", err)
			client.clock.sleep(5 * time.Second)
		} else {
			client.Logger.Errorf("cipd: failed to set ref - %s", err)
			return err
		}
	}
	client.Logger.Errorf("cipd: failed set ref - deadline exceeded")
	return ErrSetRefTimeout
}

func (client *clientImpl) AttachTagsWhenReady(pin common.Pin, tags []string) error {
	err := common.ValidatePin(pin)
	if err != nil {
		return err
	}
	if len(tags) == 0 {
		return nil
	}
	for _, tag := range tags {
		client.Logger.Infof("cipd: attaching tag %s", tag)
	}
	deadline := client.clock.now().Add(TagAttachTimeout)
	for client.clock.now().Before(deadline) {
		err = client.remote.attachTags(pin, tags)
		if err == nil {
			client.Logger.Infof("cipd: all tags attached")
			return nil
		}
		if _, ok := err.(*pendingProcessingError); ok {
			client.Logger.Warningf("cipd: package instance is not ready yet - %s", err)
			client.clock.sleep(5 * time.Second)
		} else {
			client.Logger.Errorf("cipd: failed to attach tags - %s", err)
			return err
		}
	}
	client.Logger.Errorf("cipd: failed to attach tags - deadline exceeded")
	return ErrAttachTagsTimeout
}

func (client *clientImpl) FetchInstance(pin common.Pin, output io.WriteSeeker) error {
	err := common.ValidatePin(pin)
	if err != nil {
		return err
	}
	client.Logger.Infof("cipd: resolving fetch URL for %s", pin)
	fetchInfo, err := client.remote.fetchInstance(pin)
	if err == nil {
		err = client.storage.download(fetchInfo.fetchURL, output)
	}
	if err != nil {
		client.Logger.Errorf("cipd: failed to fetch %s - %s", pin, err)
		return err
	}
	client.Logger.Infof("cipd: successfully fetched %s", pin)
	return nil
}

func (client *clientImpl) FetchAndDeployInstance(pin common.Pin) error {
	err := common.ValidatePin(pin)
	if err != nil {
		return err
	}

	// Use temp file for storing package file. Delete it when done.
	var instance local.PackageInstance
	f, err := client.deployer.TempFile(pin.InstanceID)
	if err != nil {
		return err
	}
	defer func() {
		// Instance takes ownership of the file, no need to close it separately.
		if instance == nil {
			f.Close()
		}
		os.Remove(f.Name())
	}()

	// Fetch the package data to the provided storage.
	err = client.FetchInstance(pin, f)
	if err != nil {
		return err
	}

	// Open the instance, verify the instance ID.
	instance, err = local.OpenInstance(f, pin.InstanceID)
	if err != nil {
		return err
	}
	defer instance.Close()

	// Deploy it. 'defer' will take care of removing the temp file if needed.
	_, err = client.deployer.DeployInstance(instance)
	return err
}

func (client *clientImpl) ProcessEnsureFile(r io.Reader) ([]common.Pin, error) {
	lineNo := 0
	makeError := func(msg string) error {
		return fmt.Errorf("Failed to parse desired state (line %d): %s", lineNo, msg)
	}

	out := []common.Pin{}
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		lineNo++

		// Split each line into words, ignore white space.
		tokens := []string{}
		for _, chunk := range strings.Split(scanner.Text(), " ") {
			chunk = strings.TrimSpace(chunk)
			if chunk != "" {
				tokens = append(tokens, chunk)
			}
		}

		// Skip empty lines or lines starting with '#'.
		if len(tokens) == 0 || tokens[0][0] == '#' {
			continue
		}

		// Each line has a format "<package name> <version>".
		if len(tokens) != 2 {
			return nil, makeError("expecting '<package name> <version>' line")
		}
		err := common.ValidatePackageName(tokens[0])
		if err != nil {
			return nil, makeError(err.Error())
		}
		err = common.ValidateInstanceVersion(tokens[1])
		if err != nil {
			return nil, makeError(err.Error())
		}

		// Good enough.
		pin, err := client.ResolveVersion(tokens[0], tokens[1])
		if err != nil {
			return nil, err
		}
		out = append(out, pin)
	}

	return out, nil
}

func (client *clientImpl) EnsurePackages(pins []common.Pin) error {
	// Make sure a package is specified only once.
	seen := make(map[string]bool, len(pins))
	for _, p := range pins {
		if seen[p.PackageName] {
			return fmt.Errorf("Package %s is specified twice", p.PackageName)
		}
		seen[p.PackageName] = true
	}

	// Enumerate existing packages.
	existing, err := client.deployer.FindDeployed()
	if err != nil {
		return err
	}

	// Figure out what needs to be updated and deleted, log it.
	toDeploy, toDelete := buildActionPlan(pins, existing)
	if len(toDeploy) == 0 && len(toDelete) == 0 {
		client.Logger.Infof("Everything is up-to-date.")
		return nil
	}
	if len(toDeploy) != 0 {
		client.Logger.Infof("Packages to be installed:")
		for _, pin := range toDeploy {
			client.Logger.Infof("  %s", pin)
		}
	}
	if len(toDelete) != 0 {
		client.Logger.Infof("Packages to be removed:")
		for _, pin := range toDelete {
			client.Logger.Infof("  %s", pin)
		}
	}

	// Remove all unneeded stuff.
	fail := false
	for _, pin := range toDelete {
		err = client.deployer.RemoveDeployed(pin.PackageName)
		if err != nil {
			client.Logger.Errorf("Failed to remove %s - %s", pin.PackageName, err)
			fail = true
		}
	}

	// Install all new stuff.
	for _, pin := range toDeploy {
		err = client.FetchAndDeployInstance(pin)
		if err != nil {
			client.Logger.Errorf("Failed to install %s - %s", pin, err)
			fail = true
		}
	}

	if !fail {
		client.Logger.Infof("All changes applied.")
		return nil
	}
	return ErrEnsurePackagesFailed
}

////////////////////////////////////////////////////////////////////////////////
// Private structs and interfaces.

type clock interface {
	now() time.Time
	sleep(time.Duration)
}

type remote interface {
	fetchACL(packagePath string) ([]PackageACL, error)
	modifyACL(packagePath string, changes []PackageACLChange) error

	resolveVersion(packageName, version string) (common.Pin, error)

	initiateUpload(sha1 string) (*UploadSession, error)
	finalizeUpload(sessionID string) (bool, error)
	registerInstance(pin common.Pin) (*registerInstanceResponse, error)

	setRef(ref string, pin common.Pin) error
	attachTags(pin common.Pin, tags []string) error
	fetchInstance(pin common.Pin) (*fetchInstanceResponse, error)

	listPackages(path string, recursive bool) ([]string, []string, error)
}

type storage interface {
	upload(url string, data io.ReadSeeker) error
	download(url string, output io.WriteSeeker) error
}

type registerInstanceResponse struct {
	uploadSession     *UploadSession
	alreadyRegistered bool
	registeredBy      string
	registeredTs      time.Time
}

type fetchInstanceResponse struct {
	fetchURL     string
	registeredBy string
	registeredTs time.Time
}

// Private stuff.

type clockImpl struct{}

func (c *clockImpl) now() time.Time        { return time.Now() }
func (c *clockImpl) sleep(d time.Duration) { time.Sleep(d) }

// buildActionPlan is used by EnsurePackages to figure out what to install or remove.
func buildActionPlan(desired, existing []common.Pin) (toDeploy, toDelete []common.Pin) {
	// Figure out what needs to be installed or updated.
	existingMap := buildInstanceIDMap(existing)
	for _, d := range desired {
		if existingMap[d.PackageName] != d.InstanceID {
			toDeploy = append(toDeploy, d)
		}
	}

	// Figure out what needs to be removed.
	desiredMap := buildInstanceIDMap(desired)
	for _, e := range existing {
		if desiredMap[e.PackageName] == "" {
			toDelete = append(toDelete, e)
		}
	}

	return
}

// buildInstanceIDMap builds mapping {package name -> instance ID}.
func buildInstanceIDMap(pins []common.Pin) map[string]string {
	out := map[string]string{}
	for _, p := range pins {
		out[p.PackageName] = p.InstanceID
	}
	return out
}
