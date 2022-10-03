Set-PSDebug -Trace 0

$env:PYTHONPATH = (Resolve-Path "..").Path

$top_photo_folder="D:\photos"
$folder="20220930_erbeetfier"
$gpx="G:\My Drive\___gpx\20220930-151323.gpx"

$d_hx99="16:58:47-17:02:42"
$d_rx100="16:58:09-16:54:31"
$d_xt30="18:14:35-18:25:28"

$f_hx99=0
$f_rx100=0
$f_xt30=1

$folder_hx99=1
$folder_rx100=1
$folder_xt30=1

$tz="-2h"

$update=1

$cmd="python"
$params='-m', 'gpx2exif.main', 'image', '--delta-tz' ,$tz , '--clear', '--ignore-offset', '--update-time', '--kml_thumbnail_size', '350', '--ask', $gpx
if(!$update) {
    $params += "--no-update-images"
}

$base_folder=Join-Path -Path $top_photo_folder -ChildPath $folder

if($f_hx99) {
    $folder = $folder_hx99 ? "$base_folder\hx99" : $base_folder
    $params_hx99=$params + $folder, '-d', $d_hx99, '--kml', '..\temp\photos_hx99.kml'
    Write-Host "$cmd $params_hx99"

    & $cmd $params_hx99

    Write-Host "`n===============`n"
}


if($f_rx100) {
    $folder = $folder_rx100 ? "$base_folder\rx100" : $base_folder
    $params_rx100=$params + $folder, '-d', $d_rx100, '--kml', '..\temp\photos_rx100.kml'
    Write-Host "$cmd $params_rx100"

    & $cmd $params_rx100

    Write-Host "`n===============`n"
}


if($f_xt30) {
    $folder = $folder_xt30 ? "$base_folder\xt30" : $base_folder
    $params_xt30=$params + $folder, '-d', $d_xt30, '--kml', '..\temp\photos_xt30.kml'
    Write-Host "$cmd $params_xt30"

    & $cmd $params_xt30
}