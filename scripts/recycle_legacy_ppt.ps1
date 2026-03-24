param(
    [string]$Root = "E:\teaching-agent_resources\original_seed"
)

Add-Type -AssemblyName Microsoft.VisualBasic

$files = Get-ChildItem -LiteralPath $Root -Filter *.ppt -File

foreach ($file in $files) {
    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
        $file.FullName,
        [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
        [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
    )
}

Write-Output ("recycled=" + $files.Count)
