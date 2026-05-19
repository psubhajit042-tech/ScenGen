param(
    [ValidateSet("status", "baseline", "candidate", "both")]
    [string]$Mode = "status",
    [string]$AppId,
    [string]$ScenarioId,
    [string]$PythonExe = "venv\Scripts\python.exe",
    [string]$CandidateRecDir = "ocr_lab\models\candidate_finetuned\my_rec_infer"
)

$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
Set-Location $repoRoot

function Resolve-RepoPath {
    param([string]$PathValue)

    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $PathValue))
}

function Clear-OcrOverrides {
    foreach ($name in @("SCENGEN_OCR_MODEL_ROOT", "SCENGEN_OCR_MODEL_NAME", "SCENGEN_OCR_DET_DIR", "SCENGEN_OCR_CLS_DIR", "SCENGEN_OCR_REC_DIR")) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
}

function Get-ActiveRecPath {
    if (Test-Path Env:SCENGEN_OCR_REC_DIR) {
        return Resolve-RepoPath $env:SCENGEN_OCR_REC_DIR
    }

    return Resolve-RepoPath "ch_ppocr_mobile_v2.0_rec_infer"
}

function Show-OcrStatus {
    $activeMode = if (Test-Path Env:SCENGEN_OCR_REC_DIR) { "candidate" } else { "baseline" }
    Write-Host "Active OCR mode: $activeMode"
    Write-Host "Detection model: $(Resolve-RepoPath 'ch_ppocr_mobile_v2.0_det_infer')"
    Write-Host "Classifier model: $(Resolve-RepoPath 'ch_ppocr_mobile_v2.0_cls_infer')"
    Write-Host "Recognition model: $(Get-ActiveRecPath)"
}

function Invoke-ScenGenRun {
    param(
        [string]$SelectedMode,
        [string]$ResolvedPython,
        [string]$ResolvedCandidateRecDir
    )

    if ([string]::IsNullOrWhiteSpace($AppId) -or [string]::IsNullOrWhiteSpace($ScenarioId)) {
        throw "AppId and ScenarioId are required for mode '$SelectedMode'. Example: -AppId A34 -ScenarioId S8"
    }

    if (-not (Test-Path $ResolvedPython)) {
        throw "Python executable not found: $ResolvedPython"
    }

    if ($SelectedMode -eq "baseline") {
        Clear-OcrOverrides
        Write-Host "Running ScenGen with the baseline OCR model..."
    }
    elseif ($SelectedMode -eq "candidate") {
        if (-not (Test-Path $ResolvedCandidateRecDir)) {
            throw "Candidate recognition folder not found: $ResolvedCandidateRecDir"
        }
        Clear-OcrOverrides
        $env:SCENGEN_OCR_REC_DIR = $ResolvedCandidateRecDir
        Write-Host "Running ScenGen with the candidate OCR model..."
    }
    else {
        throw "Unsupported run mode: $SelectedMode"
    }

    Show-OcrStatus
    & $ResolvedPython test.py $AppId $ScenarioId
}

$resolvedPython = Resolve-RepoPath $PythonExe
$resolvedCandidateRecDir = Resolve-RepoPath $CandidateRecDir

switch ($Mode) {
    "status" {
        Show-OcrStatus
    }
    "baseline" {
        try {
            Invoke-ScenGenRun -SelectedMode "baseline" -ResolvedPython $resolvedPython -ResolvedCandidateRecDir $resolvedCandidateRecDir
        }
        finally {
            Clear-OcrOverrides
        }
    }
    "candidate" {
        try {
            Invoke-ScenGenRun -SelectedMode "candidate" -ResolvedPython $resolvedPython -ResolvedCandidateRecDir $resolvedCandidateRecDir
        }
        finally {
            Clear-OcrOverrides
        }
    }
    "both" {
        try {
            Invoke-ScenGenRun -SelectedMode "baseline" -ResolvedPython $resolvedPython -ResolvedCandidateRecDir $resolvedCandidateRecDir
            Invoke-ScenGenRun -SelectedMode "candidate" -ResolvedPython $resolvedPython -ResolvedCandidateRecDir $resolvedCandidateRecDir
        }
        finally {
            Clear-OcrOverrides
        }
    }
}
