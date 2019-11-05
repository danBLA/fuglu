#!/usr/bin/env sh

if [ -z "${DEPLOY_ENV}" ]; then
    echo "No deploy, DEPLOY_ENV is not set..."
else
    echo "tag & push CONTAINER_TEST_IMAGE: ${CONTAINER_TEST_IMAGE}"
    echo "${CI_COMMIT_SHA}" > fuglu.sha
    docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    docker pull $CONTAINER_TEST_IMAGE || docker pull $CONTAINER_RELEASE_IMAGE || true
    docker build --cache-from $CONTAINER_TEST_IMAGE --cache-from $CONTAINER_CONTAINER_RELEASE_IMAGE  \
            $CONTAINER_TEST_IMAGE -f docker/fuglu-testenv-contained/Dockerfile.alpine .
    echo "Image info:"
    docker image ls | grep -w $CONTAINER_TEST_IMAGE
    docker image ls | grep -w $CONTAINER_TEST_IMAGE
    docker push $CONTAINER_TEST_IMAGE
    if [ "$CI_COMMIT_REF_SLUG" == "master" ]; then
      echo "Tagging branch as release image $CONTAINER_RELEASE_IMAGE"
      docker tag $CONTAINER_TEST_IMAGE $CONTAINER_RELEASE_IMAGE
      docker push $CONTAINER_RELEASE_IMAGE
    fi
fi
