$targets = @()

$publicRoot = "E:\teaching-agent_resources\public_seed"
$historyRoot = "E:\teaching-agent_resources\subject_seed\history"
$mathRoot = "E:\teaching-agent_resources\subject_seed\math"
$englishRoot = "E:\teaching-agent_resources\subject_seed\english"

if (Test-Path $publicRoot) {
    $targets += Get-ChildItem -Path $publicRoot -Recurse -File -Filter *.txt
}

foreach ($root in @($historyRoot, $mathRoot, $englishRoot)) {
    if (Test-Path $root) {
        $targets += Get-ChildItem -Path $root -Recurse -File | Where-Object { $_.Extension -in ".txt", ".json" }
    }
}

$targets = $targets | Sort-Object FullName -Unique

foreach ($file in $targets) {
    Remove-Item -LiteralPath $file.FullName -Force
}

$targets | ForEach-Object { $_.FullName }
