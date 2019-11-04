#!/usr/bin/env sh

if [ -z "${DEPLOY_ENV}" ]; then
    echo "No deploy, DEPLOY_ENV is not set..."
else
    echo "tag & push CONTAINER_TEST_IMAGE: ${CONTAINER_TEST_IMAGE}"
    echo "${CI_COMMIT_SHA}" > fuglu.sha
    docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    docker build --tag $CONTAINER_TEST_IMAGE -f docker/fuglu-testenv-contained/Dockerfile.alpine .
    docker image ls | grep -w $CONTAINER_TEST_IMAGE
    docker push $CONTAINER_TEST_IMAGE
    if [ -z "$1" ]; then
      echo "no extra argument, not creating release tag"
    else
      echo "Tagging branch as release image $CONTAINER_RELEASE_IMAGE"
      docker tag $CONTAINER_TEST_IMAGE $CONTAINER_RELEASE_IMAGE
      docker push $CONTAINER_RELEASE_IMAGE
    fi
fi