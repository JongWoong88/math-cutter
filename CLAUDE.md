# CLAUDE.md

앞으로 모든 답변은 한국어로 해야합니다. 이 사실을 절대로 잊어선 안됩니다.
이 파일은 이 저장소에서 코드를 다룰 때 Claude Code(claude.ai/code) 에 대한 지침을 제공합니다.

## Project Overview

**Koong's Lab**은 개발자와 학습자를 위한 유틸리티 도구 모음 플랫폼입니다. 현재 PDF 문제지 커팅기를 포함하여 다양한 온라인 도구들을 제공하며, 확장 가능한 모듈형 아키텍처로 설계되어 있습니다.

### 브랜드 정보
- **브랜드명**: Koong's Lab
- **도메인**: www.koonglab.co.kr  
- **컨셉**: 업무 효율성을 높이는 필수 유틸리티 도구들을 한 곳에서 제공
- **타겟**: 개발자, 학습자, 교육자, 업무 효율성을 추구하는 모든 사용자

### 현재 제공 모듈
1. **PDF 문제지 커팅기** - PDF 문제지를 개별 문제 이미지로 자동 분할

## Platform Architecture

### 모듈형 구조
```
Koong's Lab Platform
├── Frontend (S3 Static Hosting)
│   ├── intro.html - 메인 허브 페이지
│   └── [module-name]/ - 각 모듈별 UI
└── Backend (AWS Lambda Functions)
    └── [module-name]/ - 각 모듈별 서버리스 함수
```

### 기술 스택
- **프론트엔드**: HTML/CSS/JavaScript, S3 Static Hosting
- **백엔드**: AWS Lambda (Python), Docker Container
- **인프라**: AWS CloudFront, ECR, S3
- **배포**: PowerShell 스크립트 자동화

## Directory Structure

```
koong-lab/
├── CLAUDE.md                    # 플랫폼 전반 문서 (이 파일)
├── README.md                    # 프로젝트 개요
├── deploy_lambda.ps1            # Lambda 배포 스크립트
├── deploy_s3.ps1               # S3 배포 스크립트
├── s3/                         # 프론트엔드 리소스
│   ├── favicon-32x32.png       # 공통 파비콘
│   ├── intro.html              # 메인 허브 페이지
│   └── [module-name]/          # 각 모듈별 UI 리소스
│       ├── CLAUDE.md           # 모듈 UI 상세 문서
│       └── *.html              # UI 페이지들
├── src/                        # 백엔드 소스 코드
│   └── [module-name]/          # 각 모듈별 Lambda 함수
│       ├── CLAUDE.md           # 모듈 백엔드 상세 문서
│       ├── Dockerfile          # 도커 이미지 설정
│       ├── app.py              # 메인 애플리케이션
│       └── requirements.txt    # Python 의존성
└── test/                       # 테스트 관련 파일들
    ├── encode_pdf.py
    ├── invoke-lambda.ps1
    └── samples/
```

### 모듈 추가 가이드

새로운 모듈을 추가할 때는 다음 구조를 따르세요:

1. **백엔드 모듈**: `src/[module-name]/`
   - Lambda 함수 코드 및 설정
   - 각 모듈의 CLAUDE.md에 아키텍처 상세 문서화

2. **프론트엔드 모듈**: `s3/[module-name]/`  
   - 웹 UI 및 정적 리소스
   - 각 모듈의 CLAUDE.md에 UI/UX 상세 문서화

3. **메인 허브 업데이트**: `s3/intro.html`
   - 새 모듈 카드 추가
   - 네비게이션 링크 연결

## Hub Page (intro.html)

### 개요
메인 허브 페이지는 Koong's Lab의 모든 유틸리티 도구들을 소개하는 랜딩 페이지입니다.

### 주요 기능
- **유틸리티 카드 표시**: 각 모듈을 카드 형태로 시각적 표현
- **네비게이션**: 개별 모듈 페이지로의 링크 제공
- **브랜드링**: 일관된 Koong's Lab 브랜드 표현
- **SEO 최적화**: 완전한 메타 태그 및 구조화된 데이터
- **반응형 디자인**: 모바일/데스크톱 최적화

### 디자인 특징
- **그리드 레이아웃**: 6개 카드를 반응형 그리드로 배치
- **인터랙션**: 호버 효과 및 페이드인 애니메이션
- **색상 체계**: 파란색 계열 (#3b82f6) 메인 컬러
- **타이포그래피**: 시스템 폰트로 가독성 최적화

## Development & Deployment

### 공통 개발 명령어
```bash
# 프론트엔드 배포
.\deploy_s3.ps1 -BucketName "your-bucket" -Region "ap-northeast-2"

# 백엔드 배포 (모듈별)
.\deploy_lambda.ps1 -ModuleName "pdf-exam-cutter" -Region "ap-northeast-2"
```

### 배포 프로세스
1. **프론트엔드**: S3에 정적 파일 동기화
2. **백엔드**: ECR에 Docker 이미지 푸시 후 Lambda 배포
3. **개별 모듈**: 독립적 배포 가능

### 테스트
각 모듈의 테스트 방법은 해당 모듈의 CLAUDE.md를 참조하세요.

## Module Documentation

각 모듈의 상세 정보는 해당 모듈 디렉토리의 CLAUDE.md를 참조하세요:

- **프론트엔드 UI**: `s3/[module-name]/CLAUDE.md`
- **백엔드 로직**: `src/[module-name]/CLAUDE.md`

### 현재 모듈 문서
- `s3/pdf-exam-cutter/CLAUDE.md` - 문제지 커팅기 UI 문서  
- `src/pdf-exam-cutter/CLAUDE.md` - 문제지 커팅기 백엔드 문서