Attribute VB_Name = "local_3RunAnalysis"
Option Explicit

' Drop-in replacement for the Stage 4 local_3RunAnalysis module. All CTI
' creation and all existing result parsing remain in the workbook; only the
' spColumn process invocation is replaced with a synchronous local-server call.
Public Sub local_RunAnalysis(lcurrentRow, sSuffix)
    Dim sSpColDir As String
    Dim sFilename As String
    Dim sInputFile As String
    Dim sOutputFile As String
    Dim sFactoredFile As String
    Dim sErrorFile As String
    Dim Response As String

    On Error GoTo AnalysisError

    sSpColDir = b_Batch1.Range("spColDir")
    sFilename = b_Batch1.Cells(lcurrentRow, 4)

    ' Preserve the original Stage 4 naming contract.
    If Len(sFilename) > 13 Then sFilename = Left$(sFilename, 13)

    sInputFile = sSpColDir & "\" & sFilename & sSuffix & ".cti"
    sOutputFile = sSpColDir & "\" & sFilename & sSuffix & ".out"
    sFactoredFile = sSpColDir & "\" & sFilename & sSuffix & "-factored.txt"
    sErrorFile = sSpColDir & "\" & sFilename & sSuffix & ".txt - error.log"

    ' Prevent a failed request from allowing the old parser to consume stale
    ' artifacts from an earlier run.
    If FileFolderExists(sOutputFile) Then Kill sOutputFile
    If FileFolderExists(sFactoredFile) Then Kill sFactoredFile
    If FileFolderExists(sErrorFile) Then Kill sErrorFile

    If Not PMMServerIsHealthy() Then
        Err.Raise vbObjectError + 2110, "local_RunAnalysis", _
            "PMM Engine is not available at http://127.0.0.1:3000"
    End If

    Response = RunPMMLocalAnalysis(sInputFile)
    Exit Sub

AnalysisError:
    lErrorFlag = 1
    MsgBox "PMM analysis failed for " & sFilename & sSuffix & ": " & _
        Err.Description, vbCritical, "PMM Engine"
End Sub
