// Declarative pipeline for task-manager-ci (Entrega 2: Integracion Continua con Jenkins).
//
// Flow: commit -> GitHub -> Jenkins (Poll SCM) -> Checkout -> Build -> Lint ->
//       Unit Test -> Integration Test (docker compose + service-name check) -> post.
//
// Credentials are NEVER written here: the database user/password come from the
// Jenkins credential "taskmanager-db-credentials" (see jenkins/casc/jenkins.yaml).

pipeline {
    agent any

    options {
        // Checkout is an explicit stage below.
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
        // The stack uses fixed container names/ports, so builds must not overlap.
        disableConcurrentBuilds()
    }

    // The same trigger is also declared on the job (jenkins/casc/jenkins.yaml).
    // Jenkins asks GitHub for new commits about every 2 minutes (H = hashed offset).
    triggers {
        pollSCM('H/2 * * * *')
    }

    environment {
        // Injects DB_CREDS_USR and DB_CREDS_PSW; Jenkins masks both in the console.
        // They are mapped to POSTGRES_USER / POSTGRES_PASSWORD inside each sh block
        // (shell expansion), never with Groovy interpolation, which would leak them.
        DB_CREDS = credentials('taskmanager-db-credentials')
        POSTGRES_DB = 'tasks'
        // Dedicated Compose project: never collides with a developer stack.
        COMPOSE_PROJECT_NAME = 'tmci-jenkins'
        // 0 = Docker picks a free host port, so port 8000 of the host is not needed.
        API_PORT = '0'
        API_IMAGE = 'task-manager-api'
        TEST_IMAGE = 'task-manager-api-test'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh '''
                    echo "Commit:  $(git rev-parse --short HEAD)"
                    echo "Message: $(git log -1 --pretty=%s)"
                    echo "Author:  $(git log -1 --pretty=%an)"
                '''
            }
        }

        // Builds the images of BOTH services from Entrega 1:
        //   api -> built from api/Dockerfile (container 1)
        //   db  -> official postgres image pinned in docker-compose.yml (container 2)
        stage('Build') {
            steps {
                sh '''
                    set -e
                    export POSTGRES_USER="$DB_CREDS_USR" POSTGRES_PASSWORD="$DB_CREDS_PSW"
                    docker compose build api
                    docker compose pull db
                    docker tag "${API_IMAGE}:local" "${API_IMAGE}:${BUILD_NUMBER}"
                    docker build -f api/Dockerfile.test -t "${TEST_IMAGE}:${BUILD_NUMBER}" api
                    echo "--- Images produced by this build"
                    docker image ls --filter "reference=${API_IMAGE}" --filter "reference=${TEST_IMAGE}" --filter "reference=postgres"
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    set -e
                    docker run --rm "${TEST_IMAGE}:${BUILD_NUMBER}" sh -c "ruff check . && ruff format --check ."
                '''
            }
        }

        stage('Unit Test') {
            steps {
                // pytest exit code is kept so the report can be copied out first;
                // a failing test still fails the build at the end of the script.
                sh '''
                    set +e
                    rm -rf reports && mkdir -p reports
                    docker rm -f "tmci-unit-${BUILD_NUMBER}" >/dev/null 2>&1
                    docker run --name "tmci-unit-${BUILD_NUMBER}" "${TEST_IMAGE}:${BUILD_NUMBER}"
                    rc=$?
                    docker cp "tmci-unit-${BUILD_NUMBER}:/reports/." reports/
                    docker rm -f "tmci-unit-${BUILD_NUMBER}" >/dev/null 2>&1
                    exit $rc
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                }
            }
        }

        // Starts the real two-container stack and checks that api reaches db by
        // the SERVICE NAME ("db"). Any failed check exits non-zero and fails the build.
        stage('Integration Test') {
            steps {
                sh '''
                    set -e
                    export POSTGRES_USER="$DB_CREDS_USR" POSTGRES_PASSWORD="$DB_CREDS_PSW"
                    docker compose up -d --no-build --wait --wait-timeout 120
                    docker compose ps
                    docker compose exec -T api python - < scripts/smoke_test.py
                '''
            }
            post {
                failure {
                    sh '''
                        export POSTGRES_USER="$DB_CREDS_USR" POSTGRES_PASSWORD="$DB_CREDS_PSW"
                        docker compose ps || true
                        docker compose logs --no-color --tail=80 || true
                    '''
                }
            }
        }
    }

    post {
        always {
            // Always release the containers, network and the database volume.
            sh '''
                export POSTGRES_USER="$DB_CREDS_USR" POSTGRES_PASSWORD="$DB_CREDS_PSW"
                docker compose down -v --remove-orphans || true
            '''
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
        success {
            echo "SUCCESS: build #${env.BUILD_NUMBER} - images built and the two containers communicate."
        }
        failure {
            echo "FAILURE: build #${env.BUILD_NUMBER} - see the first failed stage above."
        }
        cleanup {
            // Keep the Jenkins disk tidy: drop the per-build test image.
            sh 'docker image rm "${TEST_IMAGE}:${BUILD_NUMBER}" >/dev/null 2>&1 || true'
        }
    }
}
