# PDF 문제지 커팅기 - 백엔드 아키텍처 문서

이 문서는 PDF 문제지 커팅기 모듈의 백엔드 Lambda 함수에 대한 상세 정보를 제공합니다.

## 개요

PDF 문제지 커팅기 백엔드는 AWS Lambda에서 실행되는 서버리스 Python 애플리케이션입니다. PDF 파일을 받아 각 문제별 이미지로 분할하고 ZIP 파일로 반환하는 핵심 로직을 담당합니다.

## 아키텍처

### 전체 시스템 구조
```
[클라이언트] → [CloudFront] → [Lambda 함수] → [ECR 도커 이미지]
              (헤더 검증)     (PDF 처리)      (PyMuPDF + PIL)
                              ↓
                         [ZIP 파일 반환]
```

### Lambda 함수 구조
```
pdf-exam-cutter/
├── app.py              # 메인 애플리케이션 로직
├── Dockerfile          # 도커 이미지 설정
└── requirements.txt    # Python 의존성
```

## 인프라 구성요소

### 1. AWS Lambda
- **런타임**: Container Image (Python 3.9)
- **아키텍처**: x86_64
- **메모리**: 최소 512MB 이상 권장 (이미지 처리로 인한 높은 메모리 사용)
- **타임아웃**: 최소 5분 이상 권장 (대용량 PDF 처리 시간 고려)
- **동시 실행**: 제한 없음 (요청량에 따라 자동 스케일링)

### 2. AWS CloudFront
- **역할**: Lambda 함수의 프록시 서버
- **보안**: 커스텀 헤더 `x-origin-verify` 추가로 직접 접근 차단
- **캐싱**: 비활성화 (각 요청이 고유한 처리 결과)
- **CORS**: 크로스 오리진 요청 허용

### 3. Amazon ECR (Elastic Container Registry)
- **용도**: Docker 이미지 저장소
- **이미지 태그**: latest (배포 시 자동 업데이트)
- **플랫폼**: linux/amd64 (Lambda 호환성)

## 애플리케이션 로직

### 처리 플로우
```python
1. 요청 수신 및 검증
   ├── CloudFront 헤더 검증
   ├── JSON 페이로드 파싱
   └── Base64 디코딩

2. PDF 처리
   ├── PyMuPDF로 이미지 변환
   ├── 이미지 전처리 (여백 제거)
   ├── 자동 분할 (좌우, 상하)
   └── 품질 검증

3. 결과 생성
   ├── 이미지 리스트 생성
   ├── ZIP 파일 압축
   └── Base64 인코딩

4. 응답 반환
   ├── HTTP 헤더 설정
   └── JSON 응답 생성
```

### 핵심 알고리즘

#### 1. PDF to 이미지 변환
```python
# PyMuPDF 사용
import fitz  # PyMuPDF

doc = fitz.open(stream=pdf_bytes, filetype="pdf")
for page in doc:
    pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
    img_data = pix.tobytes("png")
```

#### 2. 이미지 전처리
```python
# 여백 제거 알고리즘
1. 상하좌우 흰색 픽셀 감지
2. 5픽셀 여백 유지하며 크롭
3. 최소 크기 검증 (전체 너비의 20% 이상)
```

#### 3. 자동 분할
```python
# 분할 로직
1. 세로축 감지: 가운데 영역의 흰색 라인 탐지
2. 좌우 분할: 세로축 기준으로 2분할
3. 가로축 감지: 행간 여백 기준 수평 분할
4. 품질 필터링: 99% 이상 흰색 이미지 제거
```

#### 4. 병렬 처리
```python
# ThreadPoolExecutor 사용
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(process_page, page) for page in pages]
    results = [future.result() for future in futures]
```

## API 사양

### 요청 형식
```json
{
    "files": ["BASE64_encoded_pdf_file"],
    "name": "filename.pdf",
    "type": "normal|inverse"
}
```

### 응답 형식 (성공)
```json
{
    "statusCode": 200,
    "headers": {
        "Content-Type": "application/zip",
        "Content-Disposition": "attachment; filename=\"result.zip\"",
        "Access-Control-Allow-Origin": "*"
    },
    "body": "BASE64_encoded_zip_file",
    "isBase64Encoded": true
}
```

### 응답 형식 (오류)
```json
{
    "statusCode": 400|403|500,
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
    },
    "body": "{\"error\": \"error_message\"}"
}
```

### 오류 코드
- **400**: 잘못된 요청 (파일 형식 오류, 필수 필드 누락)
- **403**: 인증 실패 (CloudFront 헤더 검증 실패)
- **500**: 서버 내부 오류 (처리 중 예외 발생)

## 의존성 및 라이브러리

### Python 패키지 (requirements.txt)
```
PyMuPDF==1.24.1    # PDF 처리 및 이미지 변환
Pillow==10.4.0     # 이미지 조작 및 처리
numpy==1.26.4      # 수치 연산 및 배열 처리
```

### 시스템 요구사항
- **Python**: 3.9 (AWS Lambda 런타임)
- **메모리**: 최소 512MB (권장 1GB 이상)
- **스토리지**: /tmp 디렉토리 512MB 제한
- **네트워크**: 외부 API 호출 없음 (self-contained)

## 보안 및 인증

### CloudFront 헤더 검증
```python
def verify_cloudfront_header(event):
    expected_header = os.environ.get('CLOUDFRONT_SECRET_HEADER')
    actual_header = event.get('headers', {}).get('x-origin-verify')
    return actual_header == expected_header
```

### 환경 변수
- **CLOUDFRONT_SECRET_HEADER**: CloudFront에서 전달되는 검증용 헤더 값
- **설정 방법**: Lambda 함수 환경 변수 또는 배포 시 설정

### 데이터 보안
- **파일 처리**: 메모리 내에서만 처리, 디스크 저장 없음
- **로그**: 개인정보 포함하지 않는 처리 로그만 기록
- **CORS**: 모든 Origin 허용 (공개 서비스)

## 성능 최적화

### 이미지 처리 최적화
```python
# NumPy 벡터화 연산 사용
import numpy as np

# 픽셀 데이터를 NumPy 배열로 처리
img_array = np.frombuffer(img_data, dtype=np.uint8)
# 벡터화된 연산으로 성능 향상
```

### 메모리 관리
- **스트리밍 처리**: 대용량 파일을 청크 단위로 처리
- **가비지 컬렉션**: 명시적인 객체 해제
- **메모리 모니터링**: CloudWatch 메트릭으로 사용량 추적

### 병렬 처리
- **페이지별 병렬화**: 각 PDF 페이지를 독립적으로 처리
- **워커 수**: CPU 코어 수에 맞춰 최적화
- **메모리 제한**: 동시 처리 수를 메모리 제한에 맞춰 조절

## 로깅 및 모니터링

### CloudWatch 로그
```python
# 표준 print() 함수 사용
print(f"Processing PDF with {page_count} pages")
print(f"Generated {len(images)} images")
print(f"ZIP file size: {zip_size} bytes")
```

### 메트릭 추적
- **처리 시간**: 전체 처리 소요 시간
- **메모리 사용량**: 피크 메모리 사용량
- **오류율**: 성공/실패 비율
- **파일 크기**: 입력/출력 파일 크기

### 디버깅
- **상세 로그**: 개발 환경에서 디버그 레벨 로깅
- **오류 스택**: 예외 발생 시 전체 스택 트레이스
- **처리 단계**: 각 처리 단계별 상태 로그

## 배포 및 운영

### Docker 이미지
```dockerfile
FROM public.ecr.aws/lambda/python:3.9

# 의존성 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 애플리케이션 코드
COPY app.py .

# Lambda 핸들러 설정
CMD ["app.lambda_handler"]
```

### 배포 프로세스
```bash
# 1. 도커 이미지 빌드
docker build --platform linux/amd64 -t pdf-exam-cutter .

# 2. ECR 푸시
docker tag pdf-exam-cutter:latest [ECR_URI]:latest
docker push [ECR_URI]:latest

# 3. Lambda 함수 업데이트
aws lambda update-function-code \
  --function-name pdf-exam-cutter \
  --image-uri [ECR_URI]:latest
```

### 환경별 설정
- **개발**: 로컬 Docker 환경에서 테스트
- **테스트**: 별도 Lambda 함수로 배포
- **프로덕션**: 본 서비스 Lambda 함수

## 테스트 및 검증

### 로컬 테스트
```bash
# Docker 컨테이너 실행
docker run -p 9000:8080 \
  -e CLOUDFRONT_SECRET_HEADER=test-secret \
  pdf-exam-cutter

# PowerShell 테스트 스크립트
./test/invoke-lambda.ps1 \
  -PdfPath "test/samples/sample.pdf" \
  -OutputZipPath "test/result.zip"
```

### 단위 테스트
- **PDF 파싱**: 다양한 형식의 PDF 파일 테스트
- **이미지 분할**: 알려진 결과와 비교 검증
- **오류 처리**: 잘못된 입력에 대한 적절한 오류 응답

### 성능 테스트
- **부하 테스트**: 동시 요청 처리 능력
- **메모리 테스트**: 대용량 파일 처리 시 메모리 사용량
- **시간 측정**: 파일 크기별 처리 시간

## 트러블슈팅

### 일반적인 문제
1. **메모리 부족**: Lambda 메모리 설정 증가
2. **타임아웃**: Lambda 타임아웃 설정 증가
3. **파일 크기 제한**: 6MB Base64 인코딩 제한
4. **이미지 품질**: PyMuPDF 스케일 팩터 조정

### 디버깅 방법
1. **CloudWatch 로그**: 실행 로그 확인
2. **로컬 테스트**: Docker 환경에서 재현
3. **단계별 확인**: 처리 단계별 중간 결과 검증
4. **입력 데이터**: 문제가 있는 PDF 파일 별도 분석

### 최적화 가이드
1. **메모리 효율**: 불필요한 객체 참조 제거
2. **처리 속도**: NumPy 연산으로 대체 가능한 부분 최적화
3. **병렬화**: 더 많은 병렬 처리 가능한 부분 식별
4. **알고리즘**: 분할 알고리즘의 정확도와 속도 균형