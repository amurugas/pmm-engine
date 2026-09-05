Attribute VB_Name = "PMMBridge"
Option Explicit

' Requires the xlwings Excel add-in and the pmm-engine[excel] Python package.
' Import this module into a macro-enabled copy of PMM_Starter.xlsx.
Public Sub RunPMMAnalysis()
    On Error GoTo Handler
    Application.ScreenUpdating = False
    Application.StatusBar = "Running PMM analysis in Python..."
    RunPython "import pmm_engine.excel_bridge as bridge; bridge.run_workbook()"
    ThisWorkbook.Worksheets("Results").Activate
    Application.StatusBar = "PMM analysis complete"
CleanExit:
    Application.ScreenUpdating = True
    Application.StatusBar = False
    Exit Sub
Handler:
    MsgBox "PMM analysis failed: " & Err.Description, vbCritical, "PMM Engine"
    Resume CleanExit
End Sub

Public Sub PrintPMMCalculation()
    RunPMMAnalysis
    With ThisWorkbook.Worksheets("Calculations")
        .PageSetup.Orientation = xlPortrait
        .PageSetup.Zoom = False
        .PageSetup.FitToPagesWide = 1
        .PageSetup.FitToPagesTall = False
        .PageSetup.LeftMargin = Application.InchesToPoints(0.5)
        .PageSetup.RightMargin = Application.InchesToPoints(0.5)
        .PageSetup.TopMargin = Application.InchesToPoints(0.5)
        .PageSetup.BottomMargin = Application.InchesToPoints(0.5)
        .PrintPreview
    End With
End Sub
