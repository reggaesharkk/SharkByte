param(
    [switch]$Terminal,
    [string]$GenieXPath,
    [string]$GenieXDataDir
)

$ErrorActionPreference = 'Stop'
$geniexRoot = Join-Path (Split-Path $PSScriptRoot) 'geniex-runtime'
$bundledGenieX = Join-Path $geniexRoot 'installed\geniex.exe'
$geniex = $GenieXPath
if ($geniex) {
    $geniex = (Get-Command $geniex -CommandType Application -ErrorAction Stop).Source
} elseif (Test-Path -LiteralPath $bundledGenieX) {
    $geniex = $bundledGenieX
} else {
    $geniex = (Get-Command geniex -CommandType Application -ErrorAction SilentlyContinue).Source
}
if ($geniex) {
    $model = 'qualcomm/Qwen3-0.6B'
    $address = 'http://127.0.0.1:18181'
    $cache = $GenieXDataDir
    if (-not $cache -and $geniex -eq $bundledGenieX) { $cache = Join-Path $geniexRoot 'data' }
    $serverArgs = @('--skip-update')
    if ($cache) {
        $cache = (Resolve-Path -LiteralPath $cache -ErrorAction Stop).Path
        $serverArgs += @('--data-dir', ('"{0}"' -f $cache))
    }
    $serverArgs += @('serve', '--host', '127.0.0.1:18181', '--compute', 'npu', '--think=false')
    $server = $null
    try {
        $models = Invoke-RestMethod "$address/v1/models" -TimeoutSec 2 -ErrorAction SilentlyContinue
    } catch {
        $models = $null
    }
    try {
        if (-not $models) {
            $server = Start-Process -FilePath $geniex -ArgumentList $serverArgs -WindowStyle Hidden -PassThru
            for ($attempt = 0; $attempt -lt 40 -and -not $models; $attempt++) {
                if ($server.HasExited) { throw 'The GenieX server exited during startup.' }
                try { $models = Invoke-RestMethod "$address/v1/models" -TimeoutSec 1 } catch {
                    Start-Sleep -Milliseconds 250
                }
            }
        }
        $servedModel = $models.data.id | Where-Object { $_ -eq $model -or $_ -eq "${model}:W4A16" } | Select-Object -First 1
        if (-not $servedModel) { throw "The GenieX server did not list $model. Cache ${model}:W4A16 with geniex pull using the same data directory." }
        if ($Terminal) {
            $demo = Join-Path $PSScriptRoot 'sharkbyte_terminal.py'
            if ($MyInvocation.ExpectingInput) {
                $input | python -X utf8 -B $demo --geniex-model $servedModel
            } else {
                python -X utf8 -B $demo --geniex-model $servedModel
            }
        } else {
            python -B (Join-Path $PSScriptRoot 'sharkbyte_chat.py') --endpoint "$address/v1/chat/completions" --model $servedModel
        }
        exit $LASTEXITCODE
    } finally {
        if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id }
    }
}
if ($Terminal) { throw 'Install GenieX for Windows and add geniex to PATH, or pass -GenieXPath.' }
$model = 'qwen2.5-0.5b-instruct-qnn-npu'
$service = foundry server status -o json | ConvertFrom-Json
if (-not $service.running) {
    foundry server start
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $service = foundry server status -o json | ConvertFrom-Json
}
$address = $service.webUrls | Where-Object { $_ -match '^http://127\.0\.0\.1:\d+$' } | Select-Object -First 1
if (-not $address) { throw 'Foundry did not report a local HTTP address.' }

$variants = (foundry model list --cached --device npu --variants -o json | ConvertFrom-Json).variants
$variant = $variants | Where-Object { $_.variantName -eq $model } | Select-Object -First 1
if (-not $variant) {
    foundry model download $model
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $variants = (foundry model list --cached --device npu --variants -o json | ConvertFrom-Json).variants
    $variant = $variants | Where-Object { $_.variantName -eq $model } | Select-Object -First 1
}
if (-not $variant.variantId) { throw 'The NPU model is missing from the Foundry cache.' }
foundry model load $variant.variantId
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -B (Join-Path $PSScriptRoot 'sharkbyte_chat.py') --endpoint "$address/v1/chat/completions" --model $variant.variantId
exit $LASTEXITCODE
