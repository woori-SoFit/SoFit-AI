pipeline {
    agent any

    environment {
        REGISTRY = '172.21.33.225:5000'
        APP_SERVER = '172.21.33.238'
        IMAGE_NAME = 'sofit-ai'
    }

    stages {
        stage('브랜치 필터') {
            steps {
                script {
                    // main, dev 브랜치에서만 파이프라인을 실행합니다.
                    // feat/* 등 작업 브랜치는 PR 단계에서 빌드하지 않습니다.
                    if (env.BRANCH_NAME != 'main' && env.BRANCH_NAME != 'dev') {
                        echo "빌드 대상 브랜치가 아닙니다: ${env.BRANCH_NAME} — 파이프라인을 건너뜁니다."
                        currentBuild.result = 'NOT_BUILT'
                        error("빌드 대상 브랜치 아님 (main, dev만 허용)")
                    }
                    echo "빌드 대상 브랜치 확인: ${env.BRANCH_NAME}"
                }
            }
        }

        stage('Checkout') {
            steps {
                // 멀티브랜치에서는 현재 브랜치에 맞는 소스를 자동으로 가져옵니다.
                checkout scm
            }
        }

        stage('Prepare Model') {
            steps {
                echo '모델 파일을 준비하는 단계입니다.'
                // 나중에 아래 주석을 풀고 모델 다운로드 링크를 넣으세요.
                // sh 'wget -O serving/models/scb_model_v1.pkl [URL]'
            }
        }

        stage('Docker Build & Push') {
            steps {
                script {
                    // 브랜치 이름을 그대로 태그로 사용 (main, dev만 도달하므로 한글 변환 불필요)
                    def branchTag = env.BRANCH_NAME
                    sh """
                        docker build -t $REGISTRY/$IMAGE_NAME:${branchTag} -f serving/Dockerfile .
                        docker push $REGISTRY/$IMAGE_NAME:${branchTag}
                    """
                }
            }
        }

        stage('Deploy') {
            // main 브랜치일 때만 온프레미스 서버에 배포합니다.
            // dev 브랜치는 Build & Push까지만 수행합니다.
            when {
                branch 'main'
            }
            steps {
                sshagent(['sofit-app-ssh']) {
                    sh '''
                        ssh -o StrictHostKeyChecking=no ubuntu@$APP_SERVER "
                            docker pull $REGISTRY/$IMAGE_NAME:main &&
                            docker tag $REGISTRY/$IMAGE_NAME:main $REGISTRY/$IMAGE_NAME:latest &&
                            docker-compose -f /home/ubuntu/docker-compose.yml up -d sofit-ai
                        "
                    '''
                }
            }
        }
    }

    post {
        success { echo "${env.BRANCH_NAME} 브랜치 빌드 성공" }
        failure { echo "${env.BRANCH_NAME} 브랜치 빌드 실패" }
        not_built { echo "${env.BRANCH_NAME} 브랜치는 빌드 대상이 아닙니다." }
    }
}
