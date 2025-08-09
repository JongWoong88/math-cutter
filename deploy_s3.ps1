# S3 Static Website Deployment Script
# Synchronize entire s3/ directory with S3 bucket (directory sync)
# 
# NOTE: S3 static website hosting should be configured once in AWS Console:
#       1. S3 Console -> Select Bucket -> Properties -> Static Website Hosting -> Enable
#       2. Index document: intro.html
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
$SOURCE_DIR = "s3"                                # Local directory to sync

Write-Host "=== S3 Directory Sync Started ===" -ForegroundColor Green
Write-Host "Bucket: $S3_BUCKET_NAME"
Write-Host "Region: $AWS_REGION"
Write-Host "Source: $SOURCE_DIR/ -> s3://$S3_BUCKET_NAME/"
Write-Host ""

# Check source directory existence
if (-not (Test-Path $SOURCE_DIR -PathType Container)) {
    Write-Host "Error: Source directory not found: $SOURCE_DIR" -ForegroundColor Red
    $currentPath = Get-Location
    Write-Host "  Current path: $currentPath" -ForegroundColor Gray
    exit 1
}

# List files to be synchronized
Write-Host "Files to be synchronized:" -ForegroundColor Yellow
Get-ChildItem -Path $SOURCE_DIR -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Substring((Resolve-Path $SOURCE_DIR).Path.Length + 1)
    Write-Host "  + $relativePath" -ForegroundColor Gray
}
Write-Host ""

# Synchronize directory to S3 with delete option
Write-Host "Synchronizing directory to S3..." -ForegroundColor Yellow
try {
    # Use aws s3 sync with --delete to remove files not present locally
    # --content-type is not available for sync, so we'll set it via metadata later for HTML files
    aws s3 sync "$SOURCE_DIR" "s3://$S3_BUCKET_NAME/" --delete --region "$AWS_REGION"
    if ($LASTEXITCODE -ne 0) { throw "S3 sync failed" }
    Write-Host "Success: S3 sync completed" -ForegroundColor Green
    
    # Set proper content types for HTML files
    Write-Host "Setting content types for HTML files..." -ForegroundColor Yellow
    Get-ChildItem -Path $SOURCE_DIR -Recurse -File -Include "*.html" | ForEach-Object {
        $relativePath = $_.FullName.Substring((Resolve-Path $SOURCE_DIR).Path.Length + 1) -replace '\\', '/'
        Write-Host "  Setting content-type for: $relativePath" -ForegroundColor Gray
        aws s3api copy-object --bucket "$S3_BUCKET_NAME" --copy-source "$S3_BUCKET_NAME/$relativePath" --key "$relativePath" --content-type "text/html" --metadata-directive "REPLACE" --region "$AWS_REGION" | Out-Null
    }
    
} catch {
    Write-Host "Error: S3 sync failed: $_" -ForegroundColor Red
    Write-Host "  - Check if S3 bucket exists" -ForegroundColor Red
    Write-Host "  - Check S3 write permissions" -ForegroundColor Red
    Write-Host "  - Check AWS credentials" -ForegroundColor Red
    exit 1
}

# Verify deployment
Write-Host "`nVerifying deployment status..." -ForegroundColor Yellow
try {
    # List all objects in the bucket to verify sync
    $s3Objects = aws s3 ls "s3://$S3_BUCKET_NAME/" --recursive --region "$AWS_REGION"
    if ($s3Objects) {
        Write-Host "Success: Files deployed successfully" -ForegroundColor Green
        $s3Objects | ForEach-Object {
            $parts = $_ -split '\s+', 4
            if ($parts.Length -ge 4) {
                $size = $parts[2]
                $filename = $parts[3]
                Write-Host "  ✓ $filename ($size bytes)" -ForegroundColor Gray
            }
        }
        
        # Verify index document
        $indexFile = "intro.html"
        $indexExists = aws s3api head-object --bucket "$S3_BUCKET_NAME" --key "$indexFile" --region "$AWS_REGION" 2>$null
        if ($indexExists) {
            Write-Host "`n  Index document '$indexFile' is available" -ForegroundColor Green
        } else {
            Write-Host "`n  Warning: Index document '$indexFile' not found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Warning: No files found in bucket or verification failed" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error: Deployment verification failed" -ForegroundColor Red
}

Write-Host "`n=== S3 Deployment Complete! ===" -ForegroundColor Green
Write-Host "Directory successfully synchronized to S3 bucket '$S3_BUCKET_NAME'." -ForegroundColor Green
Write-Host "`nDeployment Summary:" -ForegroundColor Yellow
Write-Host "  - Source: $SOURCE_DIR/" -ForegroundColor Gray
Write-Host "  - Destination: s3://$S3_BUCKET_NAME/" -ForegroundColor Gray
Write-Host "  - Sync mode: Full synchronization with delete" -ForegroundColor Gray
Write-Host "`nTip: If static website hosting is enabled, check:" -ForegroundColor Yellow
Write-Host "http://$S3_BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com" -ForegroundColor Blue