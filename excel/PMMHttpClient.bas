Attribute VB_Name = "PMMHttpClient"
Option Explicit

' Thin network transport for the future intranet workflow. Keep engineering
' calculations on the server. The workbook should build the versioned JSON
' payload and parse the response with a reviewed JSON module such as VBA-JSON.

Private Const DEFAULT_API_URL As String = "http://127.0.0.1:3000"

Public Function PostPMMJson(ByVal Payload As String, Optional ByVal BaseUrl As String = "") As String
    Dim Request As Object
    Dim Endpoint As String

    If Len(BaseUrl) = 0 Then BaseUrl = DEFAULT_API_URL
    Endpoint = BaseUrl & "/api/v1/analyze"

    Set Request = CreateObject("WinHttp.WinHttpRequest.5.1")
    Request.SetTimeouts 5000, 5000, 10000, 120000
    Request.Open "POST", Endpoint, False
    Request.SetRequestHeader "Content-Type", "application/json"
    Request.SetRequestHeader "Accept", "application/json"
    Request.SetRequestHeader "X-PMM-Client", "Excel-VBA"

    ' Use the current Windows user's credentials when the intranet endpoint is
    ' protected by IIS Windows Authentication.
    Request.SetAutoLogonPolicy 0
    Request.Send Payload

    If Request.Status < 200 Or Request.Status >= 300 Then
        Err.Raise vbObjectError + 2101, "PostPMMJson", _
            "PMM server returned HTTP " & Request.Status & ": " & Request.ResponseText
    End If
    PostPMMJson = Request.ResponseText
End Function

Public Sub SavePMMReportJson(ByVal Payload As String, ByVal OutputPath As String, Optional ByVal BaseUrl As String = "")
    Dim Request As Object
    Dim Stream As Object
    Dim Endpoint As String

    If Len(BaseUrl) = 0 Then BaseUrl = DEFAULT_API_URL
    Endpoint = BaseUrl & "/api/v1/report"

    Set Request = CreateObject("WinHttp.WinHttpRequest.5.1")
    Request.SetTimeouts 5000, 5000, 10000, 120000
    Request.Open "POST", Endpoint, False
    Request.SetRequestHeader "Content-Type", "application/json"
    Request.SetRequestHeader "Accept", "application/pdf"
    Request.SetRequestHeader "X-PMM-Client", "Excel-VBA"
    Request.SetAutoLogonPolicy 0
    Request.Send Payload

    If Request.Status < 200 Or Request.Status >= 300 Then
        Err.Raise vbObjectError + 2102, "SavePMMReportJson", _
            "PMM report server returned HTTP " & Request.Status & ": " & Request.ResponseText
    End If

    Set Stream = CreateObject("ADODB.Stream")
    Stream.Type = 1
    Stream.Open
    Stream.Write Request.ResponseBody
    Stream.SaveToFile OutputPath, 2
    Stream.Close
End Sub

Public Function PMMServerIsHealthy(Optional ByVal BaseUrl As String = "") As Boolean
    Dim Request As Object
    If Len(BaseUrl) = 0 Then BaseUrl = DEFAULT_API_URL
    On Error GoTo Unhealthy
    Set Request = CreateObject("WinHttp.WinHttpRequest.5.1")
    Request.SetTimeouts 2000, 2000, 2000, 2000
    Request.Open "GET", BaseUrl & "/api/health", False
    Request.SetAutoLogonPolicy 0
    Request.Send
    PMMServerIsHealthy = (Request.Status = 200)
    Exit Function
Unhealthy:
    PMMServerIsHealthy = False
End Function
