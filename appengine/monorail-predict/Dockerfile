FROM gcr.io/google_appengine/python
RUN virtualenv /env -p python

# Set virtualenv environment variables. This is equivalent to running
# source /env/bin/activate
ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH
ADD . /app

RUN apt-get update
RUN apt-get install -y python curl python-pip

RUN curl https://dl.google.com/dl/cloudsdk/release/install_google_cloud_sdk.bash > install.sh
RUN mkdir -p /sdk
RUN bash ./install.sh --disable-prompts --install-dir /sdk
RUN /sdk/google-cloud-sdk/bin/gcloud components update --quiet app app-engine-python

RUN pip install gunicorn flask futures

RUN apt-get update; \
    apt-get install -y \
      build-essential python-dev python-setuptools \
      libatlas-dev libatlas3gf-base

RUN update-alternatives --set libblas.so.3 \
      /usr/lib/atlas-base/atlas/libblas.so.3; \
    update-alternatives --set liblapack.so.3 \
      /usr/lib/atlas-base/atlas/liblapack.so.3

RUN pip install -U numpy scipy scikit-learn
RUN pip install --upgrade google-api-python-client
RUN pip install oauth2client==3.0.0

ENTRYPOINT [ "gunicorn", "-b", ":8080", "--workers", "1", "--threads", "5", "service:app" ]

EXPOSE 8080
