pipeline {
    agent any
    environment {
        REGISTRY    = '172.21.33.225:5000'
        APP_SERVER  = '172.21.33.238'
        IMAGE_NAME  = 'sofit-ai'
        BRANCH_TAG  = 'refactoring'
    }
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Prepare Model') {
            steps {
                echo '모델 파일을 준비하는 단계입니다.'
                // sh 'wget -O serving/models/scb_model_v1.pkl [URL]'
            }
        }
        stage('Docker Build & Push') {
            steps {
                sh """
                    docker build --no-cache -t $REGISTRY/$IMAGE_NAME:$BRANCH_TAG -f serving/Dockerfile .
                    docker push $REGISTRY/$IMAGE_NAME:$BRANCH_TAG
                """
            }
        }
        stage('Deploy') {
            steps {
                sshagent(['sofit-app-ssh']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ubuntu@$APP_SERVER '
                            docker pull $REGISTRY/$IMAGE_NAME:main &&
                            docker tag  $REGISTRY/$IMAGE_NAME:main $REGISTRY/$IMAGE_NAME:latest &&
                            docker-compose -f /home/ubuntu/docker-compose.yml up -d sofit-ai
                        '
                    """
                }
            }
        }
    }
    post {
        always {
            sh 'docker image prune -f'  // 매 빌드 후 찌꺼기 자동 정리
        }
        success { echo "refactoring 브랜치 빌드/배포 성공" }
        failure { echo "refactoring 브랜치 빌드/배포 실패" }
    }
}
