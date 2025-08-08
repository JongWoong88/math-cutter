# AWS Lambda에서 제공하는 공식 Python 3.9 런타임 이미지를 기반으로 합니다.
FROM public.ecr.aws/lambda/python:3.9

# 작업 디렉토리를 /var/task로 설정합니다. Lambda는 이 디렉토리에서 코드를 실행합니다.
WORKDIR /var/task

# 의존성 파일을 먼저 복사합니다.
# 이렇게 하면 코드 변경 시마다 의존성을 새로 설치하지 않아 Docker 빌드 캐시를 효율적으로 사용할 수 있습니다.
COPY requirements.txt .

# pip를 최신 버전으로 업그레이드하고 requirements.txt에 명시된 의존성을 설치합니다.
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 애플리케이션 소스 코드를 컨테이너에 복사합니다.
COPY app.py .

# Lambda가 호출할 핸들러 함수를 지정합니다.
# "app.handler"는 app.py 파일의 handler 함수를 의미합니다.
CMD [ "app.handler" ]

