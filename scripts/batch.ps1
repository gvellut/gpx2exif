Set-PSDebug -Trace 0

$env:PYTHONPATH = (Resolve-Path "..").Path

$folder="20220705_arlevecornu"
$gpx="G:\My Drive\___gpx\20220715-085719.gpx"

$d_hx99="18:34:02-18:37:57"
$d_rx100="18:33:01-18:29:38"
$d_xt30="18:33:48-18:43:02"

$f_hx99=1
$f_rx100=0
$f_xt30=1

$tz="-2h"

$update=1

$cmd="python"
$params='-m', 'gpx2exif.main', 'image', '--delta-tz' ,$tz , '--clear', '--ignore-offset', '--update-time', '--kml_thumbnail_size', '350', '--ask', $gpx
if(!$update) {
    $params += "--no-update-images"
}

$base_folder="C:\Users\gvellut\Pictures\camera\$folder"

if($f_hx99) {
    $params_hx99=$params + "$base_folder\hx99", '-d', $d_hx99, '--kml', '..\temp\photos_hx99.kml'
    Write-Host "$cmd $params_hx99"

    & $cmd $params_hx99

    Write-Host "`n===============`n"
}


if($f_rx100) {
    $params_rx100=$params + "$base_folder\rx100", '-d', $d_rx100, '--kml', '..\temp\photos_rx100.kml'
    Write-Host "$cmd $params_rx100"

    & $cmd $params_rx100

    Write-Host "`n===============`n"
}


if($f_xt30) {
    $params_xt30=$params + "$base_folder\xt30", '-d', $d_xt30, '--kml', '..\temp\photos_xt30.kml'
    Write-Host "$cmd $params_xt30"

    & $cmd $params_xt30
}