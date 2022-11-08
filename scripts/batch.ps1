Set-PSDebug -Trace 0

$env:PYTHONPATH = (Resolve-Path "..").Path

$top_photo_folder="D:\photos"
$folder="20221107_pourgnybellegarde"
$gpx="G:\My Drive\___gpx\20221107-073309.gpx"

$d_hx99="17:49:11-18:52:59"
$d_rx100="16:52:39-17:48:49"
$d_xt30="16:52:10-17:03:08"

$f_hx99=0
$f_rx100=1
$f_xt30=1

$folder_hx99=1
$folder_rx100=1
$folder_xt30=1

$tz="-1h"

$update=1

$cmd="python"
$params='-m', 'gpx2exif.main', 'image', '--delta-tz' ,$tz , '--clear', '--ignore-offset', '--update-time', '--kml_thumbnail_size', '350', '--ask', $gpx
if(!$update) {
    $params += "--no-update-images"
}

$base_folder=Join-Path -Path $top_photo_folder -ChildPath $folder

if($f_hx99) {
    $p_folder = $folder_hx99 ? "$base_folder\hx99" : $base_folder
    $params_hx99=$params + $p_folder, '-d', $d_hx99, '--kml', "..\temp\photos_$(folder)_hx99.kml"
    Write-Host "$cmd $params_hx99"

    & $cmd $params_hx99

    Write-Host "`n===============`n"
}


if($f_rx100) {
    $p_folder = $folder_rx100 ? "$base_folder\rx100" : $base_folder
    $params_rx100=$params + $p_folder, '-d', $d_rx100, '--kml', "..\temp\photos_$(folder)_rx100.kml"
    Write-Host "$cmd $params_rx100"

    & $cmd $params_rx100

    Write-Host "`n===============`n"
}


if($f_xt30) {
    $p_folder = $folder_xt30 ? "$base_folder\xt30" : $base_folder
    $params_xt30=$params + $p_folder, '-d', $d_xt30, '--kml', "..\temp\photos_$(folder)_xt30.kml"
    Write-Host "$cmd $params_xt30"

    & $cmd $params_xt30
}