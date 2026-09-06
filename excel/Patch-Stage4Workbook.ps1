[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $InputWorkbook,

    [Parameter(Mandatory = $true)]
    [string] $OutputWorkbook,

    [string] $LoadingDirectory = "",
    [string] $GeometryDirectory = "",
    [string] $ReinforcementDirectory = "",
    [string] $AnalysisDirectory = "",
    [switch] $Force
)

$ErrorActionPreference = "Stop"

function Replace-RequiredText {
    param(
        [Parameter(Mandatory = $true)] [string] $Text,
        [Parameter(Mandatory = $true)] [string] $Old,
        [Parameter(Mandatory = $true)] [string] $New,
        [Parameter(Mandatory = $true)] [string] $Description
    )
    if (-not $Text.Contains($Old)) {
        throw "Could not find expected VBA text for $Description. The workbook version may have changed."
    }
    return $Text.Replace($Old, $New)
}

function Replace-RequiredRegex {
    param(
        [Parameter(Mandatory = $true)] [string] $Text,
        [Parameter(Mandatory = $true)] [string] $Pattern,
        [Parameter(Mandatory = $true)] [string] $New,
        [Parameter(Mandatory = $true)] [string] $Description
    )
    if (-not [regex]::IsMatch($Text, $Pattern)) {
        throw "Could not find expected VBA text for $Description. The workbook version may have changed."
    }
    return [regex]::Replace($Text, $Pattern, $New, 1)
}

function Set-ModuleText {
    param($Workbook, [string] $ModuleName, [string] $Text)
    $component = $Workbook.VBProject.VBComponents.Item($ModuleName)
    $module = $component.CodeModule
    if ($module.CountOfLines -gt 0) {
        $module.DeleteLines(1, $module.CountOfLines)
    }
    $module.AddFromString($Text)
}

function Remove-ModuleIfPresent {
    param($Workbook, [string] $ModuleName)
    try {
        $component = $Workbook.VBProject.VBComponents.Item($ModuleName)
        $Workbook.VBProject.VBComponents.Remove($component)
    }
    catch {
        if ($_.Exception.Message -notmatch "Subscript out of range") { throw }
    }
}

$source = (Resolve-Path -LiteralPath $InputWorkbook).Path
$destination = [IO.Path]::GetFullPath($OutputWorkbook)
if ([IO.Path]::GetExtension($destination).ToLowerInvariant() -ne ".xlsm") {
    throw "OutputWorkbook must use the .xlsm extension."
}
if ([IO.File]::Exists($destination) -and -not $Force) {
    throw "Output workbook already exists. Pass -Force to replace it: $destination"
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
Copy-Item -LiteralPath $source -Destination $destination -Force:$Force

$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $workbook = $excel.Workbooks.Open($destination, 0, $false)

    $batchComponent = $workbook.VBProject.VBComponents.Item("local_1BatchRun")
    $batchModule = $batchComponent.CodeModule
    $batchText = $batchModule.Lines(1, $batchModule.CountOfLines)
    $newCheck = @"
    ' Check that the local PMM analysis service is available
    If Not PMMServerIsHealthy() Then
        MsgBox "PMM Engine is not available at http://127.0.0.1:3000"
        Application.Calculation = xlCalculationAutomatic
        Exit Sub
    End If
"@
    $preflightPattern = "(?ms)^    ' Check that spColumn\.exe exists\r?\n.*?^    End If\r?\n"
    $batchText = Replace-RequiredRegex $batchText $preflightPattern $newCheck "BatchRun server preflight"
    $batchText = Replace-RequiredText $batchText `
        '            Call local_RunAnalysis(lcurrentRow, "-Bi")' `
        "            Call local_RunAnalysis(lcurrentRow, ""-Bi"")`r`n            If lErrorFlag = 1 Then GoTo CleanExit" `
        "BatchRun biaxial error handling"
    $batchText = Replace-RequiredText $batchText `
        '                Call local_RunAnalysis(lcurrentRow, "-X")' `
        "                Call local_RunAnalysis(lcurrentRow, ""-X"")`r`n                If lErrorFlag = 1 Then GoTo CleanExit" `
        "BatchRun X-axis error handling"
    $batchText = Replace-RequiredText $batchText `
        '                Call local_RunAnalysis(lcurrentRow, "-Y")' `
        "                Call local_RunAnalysis(lcurrentRow, ""-Y"")`r`n                If lErrorFlag = 1 Then GoTo CleanExit" `
        "BatchRun Y-axis error handling"
    Set-ModuleText $workbook "local_1BatchRun" $batchText

    $oneComponent = $workbook.VBProject.VBComponents.Item("local_7RunOne")
    $oneModule = $oneComponent.CodeModule
    $oneText = $oneModule.Lines(1, $oneModule.CountOfLines)
    $oneText = Replace-RequiredRegex $oneText $preflightPattern $newCheck "RunOne server preflight"
    $oneText = Replace-RequiredText $oneText `
        '    Call local_RunAnalysis(lcurrentRow, "-Bi")' `
        "    Call local_RunAnalysis(lcurrentRow, ""-Bi"")`r`n    If lErrorFlag = 1 Then GoTo CleanExit" `
        "RunOne biaxial error handling"
    $oneText = Replace-RequiredText $oneText `
        '    Call local_RunAnalysis(lcurrentRow, "-X")' `
        "    Call local_RunAnalysis(lcurrentRow, ""-X"")`r`n    If lErrorFlag = 1 Then GoTo CleanExit" `
        "RunOne X-axis error handling"
    $oneText = Replace-RequiredText $oneText `
        '    Call local_RunAnalysis(lcurrentRow, "-Y")' `
        "    Call local_RunAnalysis(lcurrentRow, ""-Y"")`r`n    If lErrorFlag = 1 Then GoTo CleanExit" `
        "RunOne Y-axis error handling"
    Set-ModuleText $workbook "local_7RunOne" $oneText

    Remove-ModuleIfPresent $workbook "local_3RunAnalysis"
    $workbook.VBProject.VBComponents.Import(
        (Join-Path $PSScriptRoot "Stage4LocalRunAnalysis.bas")
    ) | Out-Null
    Remove-ModuleIfPresent $workbook "PMMHttpClient"
    $workbook.VBProject.VBComponents.Import(
        (Join-Path $PSScriptRoot "PMMHttpClient.bas")
    ) | Out-Null

    $summary = $workbook.Worksheets.Item("Design Summary")
    if ($LoadingDirectory) { $summary.Range("LoadingDir").Value2 = [IO.Path]::GetFullPath($LoadingDirectory) }
    if ($GeometryDirectory) { $summary.Range("GeomDir").Value2 = [IO.Path]::GetFullPath($GeometryDirectory) }
    if ($ReinforcementDirectory) { $summary.Range("ReinfDir").Value2 = [IO.Path]::GetFullPath($ReinforcementDirectory) }
    if ($AnalysisDirectory) { $summary.Range("spColDir").Value2 = [IO.Path]::GetFullPath($AnalysisDirectory) }

    $workbook.Save()
}
finally {
    if ($null -ne $workbook) { $workbook.Close($false) }
    if ($null -ne $excel) { $excel.Quit() }
    if ($null -ne $workbook) { [void] [Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbook) }
    if ($null -ne $excel) { [void] [Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Write-Output "Patched Stage 4 workbook: $destination"
