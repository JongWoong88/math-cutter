# CLAUDE.md

앞으로 모든 답변은 한국어로 해야합니다. 이 사실을 절대로 잊어선 안됩니다.
이 파일은 이 저장소에서 코드를 다룰 때 Claude Code(claude.ai/code) 에 대한 지침을 제공합니다.

## Project Overview

이 프로젝트는 **Koong's Lab** 브랜드 하에 운영되는 유틸리티 도구 모음으로, 주요 기능인 PDF 문제지 커팅기를 포함합니다. 

**문제지 커팅기**는 PDF로 작성된 문제지 파일을 입력받아 각 문제를 이미지 파일로 가공해주는 Lambda function입니다. 이 시스템은 AWS Lambda 환경에서 작동하며, Python으로 작성되고 Docker image로 빌드됩니다. 클라이언트로부터의 요청은 AWS CloudFront를 통해 AWS Lambda에 배포한 함수 URL을 통해 전달되며, 최종적으로 도커 이미지에 구현된 함수에 의해 처리됩니다.

### 사이트 구조
- **메인 허브**: `intro.html` - Koong's Lab의 다양한 유틸리티 도구들을 소개하는 랜딩 페이지
- **문제지 커팅기**: `pdf-exam-cutter/utility.html` - PDF 문제지 분할 전용 도구 페이지

## Architecture

```
[클라이언트] → [CloudFront] → [Lambda 함수] → [ECR 도커 이미지]
              (헤더 검증)     (PDF 처리)      (PyMuPDF + PIL)
                              ↓
                         [ZIP 파일 반환]
```

## Infrastructure

### 1. AWS Lambda
애플리케이션의 핵심 로직이 실행되는 **서버리스 컴퓨팅 서비스**입니다. 도커 이미지로 패키징된 애플리케이션이 이 환경에서 실행되며, 요청이 있을 때만 활성화되어 비용 효율성을 극대화합니다. CloudFront에 미리 정의된 헤더값을 확인하여 요청이 CloudFront의 엔드포인트를 통해 들어왔는지 검증합니다.

### 2. AWS CloudFront
클라이언트가 람다함수를 호출하기위한 엔드포인트를 제공합니다. 람다함수의 프록시 서버 역할을 합니다. 람다함수가 요청을 검증 할 때 사용하는 커스텀 헤더 값`x-origin-verify`을 추가합니다.

### 2. Amazon ECR (Elastic Container Registry)
도커 이미지가 저장되는 **AWS의 도커 이미지 레지스트리**입니다. 로컬에서 개발 및 빌드된 이미지는 이 ECR에 푸시되며, Lambda 함수가 이 이미지를 가져와 사용합니다.

## Request Flow

1. **요청 시작**: 사용자가 배포된 AWS CloudFront의 url로 요청합니다.
2. **CloudFront 요청 수신 및 전달**: 클라이언트로부터 받은 요청을 처리합니다. 이 때 미리 정의된 커스텀 헤더 값`x-origin-verify`을 추가합니다.
3. **Lambda 함수 호출**: CloudFront가 Lambda 함수를 호출합니다. 이 과정에서 사용자의 요청 정보(헤더, 본문 등)는 **이벤트(Event) 객체** 형태로 Lambda 함수에 전달됩니다.
4. **Lambda 함수 실행**: Lambda 함수는 ECR에 저장된 도커 이미지를 기반으로 실행됩니다. 전달받은 이벤트 객체의 정보를 바탕으로 애플리케이션 로직을 수행합니다.
5.  **응답 반환**: 어플리케이션 로직이 완료되면, Lambda 함수는 처리 결과를 **JSON 형식** 등의 응답으로 CloudFront에 반환합니다.
6.  **사용자 응답**: CloudFront는 Lambda 함수로부터 받은 응답을 사용자에게 최종적으로 전달합니다.

### Application Flow

1. **PDF 입력**: Base64로 인코딩된 PDF 파일들을 수신
2. **이미지 변환**: PyMuPDF를 사용하여 PDF 각 페이지를 PNG 이미지로 변환 (1000px 고정 가로 크기)
3. **이미지 전처리**:
   - 상하좌우 흰색 여백 제거 (5픽셀 여백 유지)
   - 상단 양식 부분 제거를 위한 가로축 감지
   - 세로 분할축 감지하여 좌우 2분할
   - 세로축 끝 지점 기준으로 하단 자르기
   - 행간 여백 기준 수평 분할
4. **품질 검증**: 
   - 최소 너비 기준 (전체 너비의 20% 이상)
   - 흰색 이미지 필터링 (99% 이상 흰색 제거)
5. **색상 처리**: 요청 타입에 따라 처리
   - `normal`: 원본 색상 유지
   - `inverse`: 색반전 처리 적용
6. **결과 압축**: 모든 처리된 이미지를 ZIP 파일로 압축하여 Base64로 인코딩 반환

### Key Features

- **병렬 처리**: ThreadPoolExecutor를 사용한 페이지별 병렬 처리로 성능 최적화
- **NumPy 최적화**: 이미지 처리 알고리즘을 NumPy로 벡터화하여 성능 향상
- **보안 검증**: CloudFront 커스텀 헤더 (`x-origin-verify`)를 통한 요청 검증
- **자동 이미지 분할**: 수학 문제지의 구조를 인식하여 자동으로 문제별 이미지 생성
- **품질 필터링**: 빈 이미지나 너무 작은 이미지 자동 제거
- **색상 처리 옵션**: normal(원본) 또는 inverse(색반전) 모드 지원

### API Specification

- **요청**
```json
{
    "files": ["BASE64_encoded_pdf_file"],
    "name": "file_name",
    "type": "normal|inverse"
}
```

- **응답 (성공시)**
```json
{
    "statusCode": 200,
    "headers": {
        "Content-Type": "application/zip",
        "Content-Disposition": "attachment; filename=\"result.zip\""
    },
    "body": "BASE64_encoded_zip_file",
    "isBase64Encoded": true
}
```

- **응답 (오류시)**
```json
{
    "statusCode": 400|403|500,
    "body": "error_message"
}
```

## Development Commands

### 로컬 테스트
```bash
# Docker 이미지 빌드
docker build -t math-cutter ./lambda

# 로컬에서 Lambda 함수 실행 (테스트용 환경변수 설정)
docker run -p 9000:8080 -e CLOUDFRONT_SECRET_HEADER=test-local-secret math-cutter

# PowerShell을 이용한 테스트 (별도 터미널)
## 일반 모드
./test/invoke-lambda.ps1 -PdfPath "D:\docker\math_cutter\test\samples\sample.pdf" -OutputZipPath "D:\docker\math_cutter\test\samples\result.zip"
## 색반전모드
./test/invoke-lambda.ps1 -PdfPath "D:\docker\math_cutter\test\samples\sample.pdf" -OutputZipPath "D:\docker\math_cutter\test\samples\result_inverse.zip" -ImageType "inverse"
```

### PDF Base64 인코딩
```bash
# PDF 파일을 Base64로 인코딩
python test/encode_pdf.py
```

### 배포 프로세스
- 배포에는 두 종류가 있으며, 각각 독립적으로 실행됩니다.
#### 람다 함수 배포(백엔드)
1. **도커 이미지 빌드**: linux/amd64환경임을 명시해야 합니다.
2. **도커 이미지 ECR 푸시**
3. **Lambda 배포**: ECR에 저장된 최근 이미지를 불러와서 배포합니다.
#### 웹페이지 S3 배포(프론트엔드)
1. **S3 디렉토리 동기화**: `s3/` 디렉토리 전체를 S3 버킷과 동기화합니다.
   - `intro.html`: 메인 허브 페이지
   - `pdf-exam-cutter/utility.html`: 문제지 커팅기 도구 페이지
   - 기타 정적 자원 파일들

### 배포 스크립트
- deploy_lambda.ps1
- deploy_s3.ps1

## Configuration Requirements

### 환경 변수
- `CLOUDFRONT_SECRET_HEADER`: CloudFront에서 설정한 `x-origin-verify` 헤더의 값

### Lambda 함수 설정
- **런타임**: Container Image
- **아키텍처**: x86_64
- **메모리**: 최소 512MB 이상 권장
- **타임아웃**: 최소 5분 이상 권장
- **환경 변수**: `CLOUDFRONT_SECRET_HEADER` 설정 필요

### CloudFront 설정
- **원본**: Lambda 함수 URL
- **캐싱**: 비활성화 (각 요청이 고유하므로)
- **헤더 전달**: `x-origin-verify` 커스텀 헤더 추가

## Logging

print()함수를 호출하는것 만으로도 AWS CloudWatch 로그 그룹에 적재가 되도록 설계되어 있습니다. 애플리케이션 레벨에서는 print()를 통해 적절한 로그를 남기는것으로 충분합니다.

## Dependencies

### Python 패키지 (requirements.txt)
- **PyMuPDF==1.24.1**: PDF 파일을 이미지로 변환
- **Pillow==10.4.0**: 이미지 처리 및 조작
- **numpy==1.26.4**: 이미지 처리 알고리즘 최적화를 위한 배열 연산

### 시스템 요구사항
- **Python 3.9**: AWS Lambda Python 3.9 런타임 이미지 기반
- **Docker**: 컨테이너 이미지 빌드 및 실행
- **AWS CLI**: ECR 배포를 위한 AWS 명령줄 도구

## Important Notes

### 성능 고려사항
- 이미지 처리 알고리즘은 NumPy 벡터화를 통해 최적화됨
- 페이지별 병렬 처리로 다중 PDF 파일 처리 시 성능 향상
- 메모리 사용량이 큰 작업이므로 Lambda 메모리 설정 주의

### 보안 고려사항  
- CloudFront 헤더 검증을 통한 직접 접근 차단
- Base64 인코딩을 통한 안전한 데이터 전송
- 환경 변수를 통한 보안 키 관리

### 파일 명명 규칙
생성되는 이미지 파일명 형식: `pdf_{인덱스}_page_{페이지}_part{좌우구분}_sub{분할순서}.png`
- 예시: `pdf_0_page_1_part1_sub1.png` (첫 번째 PDF의 1페이지 왼쪽 첫 번째 문제)

## Frontend Website Structure

### 브랜드 정보
- **브랜드명**: Koong's Lab
- **도메인**: www.koonglab.co.kr
- **컨셉**: 개발자와 학습자를 위한 유틸리티 도구 모음

### 페이지 구조 및 SEO

#### 1. 메인 허브 페이지 (`intro.html`)
- **역할**: 유틸리티 도구들의 랜딩 페이지 및 허브
- **URL**: https://www.koonglab.co.kr/
- **제목**: "Koong's Lab - 개발자와 학습자를 위한 유틸리티 도구 모음"
- **설명**: 다양한 온라인 유틸리티 도구 모음을 소개하는 메인 페이지
- **기능**:
  - 6개 유틸리티 카테고리 카드 표시
  - 문제지 커팅기로의 네비게이션 제공
  - 향후 추가될 도구들에 대한 예고 ("Coming Soon" 기능)

#### 2. 문제지 커팅기 페이지 (`pdf-exam-cutter/utility.html`)
- **역할**: PDF 문제지 분할 전용 도구 페이지
- **URL**: https://www.koonglab.co.kr/pdf-exam-cutter/utility.html
- **제목**: "문제지 커팅기 - PDF 문제지를 개별 문제 이미지로 자동 분할 | Koong's Lab"
- **설명**: PDF 문제지를 각 문제별 이미지로 자동 분할하는 실제 도구
- **기능**:
  - PDF 파일 드래그 앤 드롭 업로드
  - 색상 처리 옵션 (일반/색반전 모드)
  - 실시간 처리 상태 표시
  - ZIP 파일 다운로드

### SEO 최적화

#### 공통 SEO 요소
- **메타 태그**: 완전한 SEO 메타 태그 세트 (description, keywords, author 등)
- **Open Graph**: 소셜 미디어 공유 최적화
- **Twitter Card**: Twitter 공유 최적화
- **구조화된 데이터**: Schema.org 마크업으로 검색 엔진 최적화
- **모바일 최적화**: 반응형 디자인 및 PWA 메타 태그

#### 사이트 구조 최적화
- **Canonical URL**: 각 페이지의 정규 URL 명시
- **사이트 계층**: 메인 사이트 → 개별 도구 구조로 Schema.org 연결
- **내부 링크**: 페이지 간 네비게이션으로 사이트 구조 강화
- **브랜드 일관성**: 모든 페이지에서 "Koong's Lab" 브랜드 명시

### UI/UX 특징

#### 디자인 시스템
- **색상 팔레트**: 파란색 계열 (#3b82f6, #007bff) 메인 컬러
- **타이포그래피**: 시스템 폰트 스택으로 가독성 최적화
- **레이아웃**: 그리드 기반 카드 레이아웃으로 일관성 유지

#### 인터랙티브 요소
- **애니메이션**: 페이드인 효과 및 호버 인터랙션
- **피드백**: 로딩 스피너, 상태 메시지, 프로그레스 표시
- **접근성**: 키보드 네비게이션 및 스크린 리더 지원

### S3 배포 설정

#### 배포 스크립트 업데이트
- **deploy_s3.ps1**: 단일 파일 업로드에서 디렉토리 전체 동기화로 변경
- **동기화 방식**: `aws s3 sync`로 완전 동기화 (--delete 옵션)
- **콘텐츠 타입**: HTML 파일에 대한 자동 Content-Type 설정
- **검증**: 배포 후 자동 검증 및 상태 보고

#### 정적 웹사이트 호스팅
- **인덱스 문서**: `intro.html`로 설정 권장
- **오류 문서**: 404 에러 페이지 설정 가능
- **캐싱**: CloudFront와 연동하여 글로벌 CDN 제공