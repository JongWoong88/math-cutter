# S3 Static Website Deployment Script
# Upload index.html to S3 bucket (file upload only)
# 
# NOTE: S3 static website hosting should be configured once in AWS Console:
#       1. S3 Console -> Select Bucket -> Properties -> Static Website Hosting -> Enable
#       2. Index document: index.html
#       3. Set bucket policy for public read access

# =============================================================================
# Parameter Definition
# =============================================================================
param(
    [Parameter(Mandatory=$true, HelpMessage="S3 bucket name")]
    [ValidateNotNullOrEmpty()]
    [string]$BucketName,
    
    [Parameter(Mandatory=$false, HelpMessage="AWS region")]
    [ValidateNotNullOrEmpty()]
    [string]$Region
)

# =============================================================================
# Variable Settings
# =============================================================================
$S3_BUCKET_NAME = $BucketName
$AWS_REGION = $Region
$HTML_FILE_PATH = "s3/index.html"                # HTML file path to upload
$S3_OBJECT_KEY = "index.html"                     # S3 object key

Write-Host "=== S3 File Upload Started ===" -ForegroundColor Green
Write-Host "Bucket: $S3_BUCKET_NAME"
Write-Host "Region: $AWS_REGION"
Write-Host "File: $HTML_FILE_PATH -> $S3_OBJECT_KEY"
Write-Host ""

# Check file existence
if (-not (Test-Path $HTML_FILE_PATH)) {
    Write-Host "Error: File not found: $HTML_FILE_PATH" -ForegroundColor Red
    $currentPath = Get-Location
    Write-Host "  Current path: $currentPath" -ForegroundColor Gray
    exit 1
}

# Upload HTML file to S3
Write-Host "Uploading HTML file to S3..." -ForegroundColor Yellow
try {
    aws s3 cp "$HTML_FILE_PATH" "s3://$S3_BUCKET_NAME/$S3_OBJECT_KEY" --content-type "text/html" --region "$AWS_REGION"
    if ($LASTEXITCODE -ne 0) { throw "S3 upload failed" }
    Write-Host "Success: S3 upload completed" -ForegroundColor Green
} catch {
    Write-Host "Error: S3 upload failed: $_" -ForegroundColor Red
    Write-Host "  - Check if S3 bucket exists" -ForegroundColor Red
    Write-Host "  - Check S3 write permissions" -ForegroundColor Red
    Write-Host "  - Check AWS credentials" -ForegroundColor Red
    exit 1
}

# Verify deployment
Write-Host "`nVerifying deployment status..." -ForegroundColor Yellow
try {
    $s3Object = aws s3api head-object --bucket "$S3_BUCKET_NAME" --key "$S3_OBJECT_KEY" --region "$AWS_REGION" 2>$null | ConvertFrom-Json
    if ($s3Object) {
        Write-Host "Success: File deployed successfully" -ForegroundColor Green
        $fileSize = $s3Object.ContentLength
        $lastModified = $s3Object.LastModified
        $contentType = $s3Object.ContentType
        Write-Host "  - File size: $fileSize bytes" -ForegroundColor Gray
        Write-Host "  - Last modified: $lastModified" -ForegroundColor Gray
        Write-Host "  - Content-Type: $contentType" -ForegroundColor Gray
    }
} catch {
    Write-Host "Error: Deployment verification failed" -ForegroundColor Red
}

Write-Host "`n=== S3 Deployment Complete! ===" -ForegroundColor Green
Write-Host "File successfully uploaded to S3 bucket '$S3_BUCKET_NAME'." -ForegroundColor Green
Write-Host "`nTip: If static website hosting is enabled, check:" -ForegroundColor Yellow
Write-Host "http://$S3_BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com" -ForegroundColor Blue