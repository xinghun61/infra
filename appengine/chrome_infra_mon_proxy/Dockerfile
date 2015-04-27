# Dockerfile extending the generic Python image with application files for a
# single application.

# gcloud preview docker pull <image tag> to make it available locally.
# To upgrade the image, run:
#   cd docker
#   docker build .
#   docker tag <image-hash> \
#       gcr.io/chrome_infra_mon_proxy/base_python27_<image-hash>
#   gcloud preview docker push <new image tag>
# And update the image tag below.
FROM gcr.io/chrome_infra_mon_proxy/base_python27_df11be121945

ADD . /app/
