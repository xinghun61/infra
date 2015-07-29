#   cd <directory of this Dockerfile>
#   docker build .    # Note the resulting image-hash.
#   docker tag <image-hash> \
#       gcr.io/chrome_infra_mon_proxy/monitoring_proxy_go_<image-hash>
#   gcloud --project chrome-infra-mon-proxy docker push \
#       gcr.io/chrome_infra_mon_proxy/monitoring_proxy_go_<image-hash>


FROM ubuntu

RUN apt-get -y install ca-certificates
RUN apt-get -y install curl
RUN mkdir /creds

ADD proxy /
ADD monitoring_proxy.sh /

CMD /monitoring_proxy.sh /proxy /creds
