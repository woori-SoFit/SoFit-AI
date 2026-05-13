pipeline {
    agent any

    environment {
        REGISTRY = '172.21.33.225:5000'
        APP_SERVER = '172.21.33.238'
        IMAGE_NAME = 'sofit-ai'
    }

    stages {
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
                    // 브랜치 이름을 태그로 사용하여 이미지 생성 (latest 오염 방지)
                    // env.BRANCH_NAME은 멀티브랜치 파이프라인에서 제공하는 환경 변수입니다.
                    def branchTag = env.BRANCH_NAME.replace("/", "-") 
                    sh """
                        docker build -t $REGISTRY/$IMAGE_NAME:${branchTag} -f serving/Dockerfile .
                        docker push $REGISTRY/$IMAGE_NAME:${branchTag}
                    """
                }
            }
        }

        stage('Deploy to Dev/Prod') {
            // [중요] 오직 main 브랜치일 때만 실제 서버에 배포를 수행합니다.
            when {
                branch 'main'
            }
            steps {
                sshagent(['sofit-app-ssh']) {
                    sh '''
                        ssh -o StrictHostKeyChecking=no ubuntu@$APP_SERVER "
                            # main 브랜치 태그인 'main' 이미지를 pull
                            docker pull $REGISTRY/$IMAGE_NAME:main &&
                            # docker-compose.yml에서 사용할 이미지 태그를 환경변수로 넘기거나, 
                            # 혹은 docker-compose 파일 자체가 latest를 보고 있다면 
                            # 배포 단계에서만 latest 태그를 추가로 부여할 수도 있습니다.
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
    }
}
