$ErrorActionPreference = 'Stop'

$base = 'http://127.0.0.1:8000'
$tag = 'smoke_' + [DateTime]::UtcNow.ToString('yyyyMMddHHmmss')

function Assert-CodeZero {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [Parameter(Mandatory = $true)][string]$Step
    )
    if ($null -eq $Response -or $Response.code -ne 0) {
        throw "$Step failed, response: $($Response | ConvertTo-Json -Depth 8)"
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Get-AuthHeader {
    param([Parameter(Mandatory = $true)][string]$Token)
    return @{ Authorization = "Bearer $Token" }
}

Write-Output '[1/12] login demo'
$loginBody = @{ username = 'demo_user' } | ConvertTo-Json
$loginResp = Invoke-RestMethod -Method Post -Uri "$base/api/v1/auth/login" -ContentType 'application/json' -Body $loginBody
Assert-CodeZero -Response $loginResp -Step 'login demo'
$demoToken = $loginResp.data.access_token
Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($demoToken)) -Message 'demo token is empty'
$demoHeaders = Get-AuthHeader -Token $demoToken

Write-Output '[2/12] classify'
$classifyBody = @{ text = 'process and thread difference' } | ConvertTo-Json
$classifyResp = Invoke-RestMethod -Method Post -Uri "$base/api/v1/ai/classify" -ContentType 'application/json' -Body $classifyBody
Assert-CodeZero -Response $classifyResp -Step 'classify'

Write-Output '[3/12] create question'
$createBody = @{
    stem = $tag
    options = @('A', 'B')
    correct_answer = 'A'
    analysis = 'api smoke test'
    ai_label = $classifyResp.data.label
    final_label = $classifyResp.data.label
    confidence = $classifyResp.data.confidence
    source_type = 'manual'
} | ConvertTo-Json -Depth 6
$createResp = Invoke-RestMethod -Method Post -Uri "$base/api/v1/questions" -Headers $demoHeaders -ContentType 'application/json' -Body $createBody
Assert-CodeZero -Response $createResp -Step 'create question'
$questionId = $createResp.data.id
if ([string]::IsNullOrWhiteSpace($questionId)) {
    throw 'create question did not return id'
}

Write-Output '[4/12] get question detail'
$detailResp = Invoke-RestMethod -Method Get -Uri "$base/api/v1/questions/$questionId" -Headers $demoHeaders
Assert-CodeZero -Response $detailResp -Step 'get question detail'
Assert-True -Condition ($detailResp.data.id -eq $questionId) -Message 'detail id mismatch'

Write-Output '[5/12] patch question'
$patchBody = @{ analysis = 'patched by smoke'; final_label = $classifyResp.data.label } | ConvertTo-Json
$patchResp = Invoke-RestMethod -Method Patch -Uri "$base/api/v1/questions/$questionId" -Headers $demoHeaders -ContentType 'application/json' -Body $patchBody
Assert-CodeZero -Response $patchResp -Step 'patch question'

Write-Output '[6/12] list questions'
$encodedTag = [uri]::EscapeDataString($tag)
$listResp = Invoke-RestMethod -Method Get -Uri "$base/api/v1/questions?page=1&size=10&keyword=$encodedTag" -Headers $demoHeaders
Assert-CodeZero -Response $listResp -Step 'list questions'
if ($listResp.data.total -lt 1) {
    throw 'list questions did not find inserted item'
}

Write-Output '[7/12] update status'
$statusBody = @{ to_status = 'reviewed' } | ConvertTo-Json
$statusResp = Invoke-RestMethod -Method Patch -Uri "$base/api/v1/questions/$questionId/status" -Headers $demoHeaders -ContentType 'application/json' -Body $statusBody
Assert-CodeZero -Response $statusResp -Step 'update status'

Write-Output '[8/12] feedback'
$feedbackBody = @{
    question_id = $questionId
    question_text = $tag
    predicted_label = 'computer_network'
    corrected_label = $classifyResp.data.label
} | ConvertTo-Json
$feedbackResp = Invoke-RestMethod -Method Post -Uri "$base/api/v1/ai/feedback" -Headers $demoHeaders -ContentType 'application/json' -Body $feedbackBody
Assert-CodeZero -Response $feedbackResp -Step 'feedback'

Write-Output '[9/12] login admin + corpus flush'
$adminLoginBody = @{ username = 'admin_user' } | ConvertTo-Json
$adminLoginResp = Invoke-RestMethod -Method Post -Uri "$base/api/v1/auth/login" -ContentType 'application/json' -Body $adminLoginBody
Assert-CodeZero -Response $adminLoginResp -Step 'login admin'
$adminToken = $adminLoginResp.data.access_token
Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($adminToken)) -Message 'admin token is empty'
$adminHeaders = Get-AuthHeader -Token $adminToken

$flushResp = Invoke-RestMethod -Method Post -Uri "$base/api/v1/admin/corpus/flush" -Headers $adminHeaders
Assert-CodeZero -Response $flushResp -Step 'trigger corpus flush'

$statusOk = $false
for ($i = 0; $i -lt 6; $i++) {
    Start-Sleep -Seconds 1
    $flushStatusResp = Invoke-RestMethod -Method Get -Uri "$base/api/v1/admin/corpus/flush/status" -Headers $adminHeaders
    Assert-CodeZero -Response $flushStatusResp -Step 'get corpus flush status'
    if (-not $flushStatusResp.data.running) {
        $statusOk = $true
        break
    }
}
Assert-True -Condition $statusOk -Message 'corpus flush did not finish in time'

Write-Output '[10/12] model versions + activate'
$versionsResp = Invoke-RestMethod -Method Get -Uri "$base/api/v1/admin/models/versions" -Headers $adminHeaders
Assert-CodeZero -Response $versionsResp -Step 'list model versions'
Assert-True -Condition ($versionsResp.data.items.Count -ge 1) -Message 'model versions is empty'

$activeVersion = ($versionsResp.data.items | Where-Object { $_.is_active -eq $true } | Select-Object -First 1)
Assert-True -Condition ($null -ne $activeVersion) -Message 'active model version not found'
$activateBody = @{ version_name = $activeVersion.version_name } | ConvertTo-Json
$activateResp = Invoke-RestMethod -Method Patch -Uri "$base/api/v1/admin/models/active" -Headers $adminHeaders -ContentType 'application/json' -Body $activateBody
Assert-CodeZero -Response $activateResp -Step 'activate model version'

Write-Output '[11/12] dashboard'
$dashResp = Invoke-RestMethod -Method Get -Uri "$base/api/v1/dashboard/subject-distribution" -Headers $demoHeaders
Assert-CodeZero -Response $dashResp -Step 'dashboard'

Write-Output '[12/12] soft delete + verify'
$deleteResp = Invoke-RestMethod -Method Delete -Uri "$base/api/v1/questions/$questionId" -Headers $demoHeaders
Assert-CodeZero -Response $deleteResp -Step 'delete question'

$is404 = $false
try {
    $null = Invoke-RestMethod -Method Get -Uri "$base/api/v1/questions/$questionId" -Headers $demoHeaders
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 404) {
        $is404 = $true
    }
}
Assert-True -Condition $is404 -Message 'deleted question detail should return 404'

Write-Output ''
Write-Output 'Smoke test passed'
Write-Output ('question_id=' + $questionId)
Write-Output ('feedback_id=' + $feedbackResp.data.feedback_id)
Write-Output ('dashboard_total=' + $dashResp.data.total)
