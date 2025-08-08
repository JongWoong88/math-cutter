<#
.SYNOPSIS
    로컬에서 실행 중인 AWS Lambda 함수를 테스트하는 스크립트입니다.

.DESCRIPTION
    지정된 PDF 파일을 Base64로 인코딩하여 AWS Lambda event 형태로 Lambda 함수에 요청을 보냅니다.
    Lambda 함수로부터 받은 Base64 인코딩된 ZIP 데이터를 디코딩하여
    지정된 경로에 ZIP 파일로 저장합니다.

.PARAMETER PdfPath
    입력할 PDF 파일의 전체 경로입니다. (필수)

.PARAMETER OutputZipPath
    결과로 생성될 ZIP 파일의 전체 경로입니다. (필수)

.PARAMETER LambdaUrl
    테스트할 Lambda 함수의 로컬 엔드포인트 URL입니다. (기본값: http://localhost:9000/2015-03-31/functions/function/invocations)

.PARAMETER ImageType
    이미지 처리 타입입니다. "normal" 또는 "inverse"를 선택할 수 있습니다. (기본값: normal)

.EXAMPLE
    .\invoke-lambda.ps1 -PdfPath "C:\Users\test\Documents\sample.pdf" -OutputZipPath "C:\Users\test\Documents\converted.zip"
    .\invoke-lambda.ps1 -PdfPath "C:\Users\test\Documents\sample.pdf" -OutputZipPath "C:\Users\test\Documents\converted.zip" -ImageType "inverse"
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$PdfPath,

    [Parameter(Mandatory=$true)]
    [string]$OutputZipPath,

    [string]$LambdaUrl = "http://localhost:9000/2015-03-31/functions/function/invocations",

    [string]$ImageType = "normal"
)

# 1. 입력된 PDF 파일이 존재하는지 확인
if (-not (Test-Path -Path $PdfPath -PathType Leaf)) {
    Write-Error "Error: PDF file not found at '$PdfPath'"
    exit 1
}

Write-Host "Starting Lambda invocation..."
Write-Host "Input PDF: $PdfPath"
Write-Host "Output ZIP: $OutputZipPath"
Write-Host "Image Type: $ImageType"


try {
    # 2. PDF 파일을 읽어 Base64 문자열로 인코딩
    Write-Host "Encoding PDF file to Base64..."
    $pdfBytes = [System.IO.File]::ReadAllBytes($PdfPath)
    $pdfB64 = [System.Convert]::ToBase64String($pdfBytes)

    # 3. Lambda에 보낼 event 객체 형태 페이로드 생성
    $bodyData = @{
        files = @($pdfB64)
        type = $ImageType
    } | ConvertTo-Json -Compress

    # 로컬 테스트용 환경변수 값 (실제 배포시에는 CloudFront에서 설정된 값 사용)
    $testSecretHeader = "test-local-secret"
    
    $payload = @{
        body = $bodyData
        headers = @{
            'Content-Type' = 'application/json'
            'x-origin-verify' = $testSecretHeader
        }
    } | ConvertTo-Json -Depth 3

    # 4. Invoke-RestMethod를 사용하여 Lambda 함수 호출 및 응답 받기
    # Invoke-RestMethod는 자동으로 $payload를 JSON 문자열로 변환하여 요청 본문에 담습니다.
    Write-Host "Invoking Lambda function at $LambdaUrl..."
    $response = Invoke-RestMethod -Uri $LambdaUrl -Method Post -Body $payload -ContentType "application/json"

    # 5. 응답에서 Base64로 인코딩된 ZIP 데이터 추출
    if ($null -eq $response.body) {
        throw "The response body from Lambda is null. Check Lambda logs for errors."
    }
    $zipB64 = $response.body

    # 6. Base64 데이터를 디코딩하여 ZIP 파일로 저장
    Write-Host "Decoding response and saving to ZIP file..."
    $zipBytes = [System.Convert]::FromBase64String($zipB64)
    [System.IO.File]::WriteAllBytes($OutputZipPath, $zipBytes)

    Write-Host "---------------------------------------------------"
    Write-Host "Success! ZIP file created at: $OutputZipPath" -ForegroundColor Green

} catch {
    Write-Error "An error occurred: $_"
    exit 1
}
