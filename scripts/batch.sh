export PYTHONPATH=`pwd`/..

top_photo_folder="/Volumes/CrucialX8/photos"
folder="20240320_saleve"
gpx="/Users/guilhem/Library/CloudStorage/GoogleDrive-guilhem.vellut@gmail.com/My Drive/___gpx/20240320-072401.gpx"

d_tz95="17:13:45-18:17:32"
d_rx100="16:18:56-17:15:03"
d_xs10="17:13:16-18:13:42"

f_tz95=1
f_rx100=0
f_xs10=1

folder_tz95=1
folder_rx100=1
folder_xs10=1

tz="-1h"

update=1

cmd="python"
params="-m gpx2exif.main image --delta-tz $tz --clear --ignore-offset --update-time --kml_thumbnail_size 350 --ask \"$gpx\""
if [[ $update -eq 0 ]];
then
    params+=" --no-update-images"
fi

base_folder="$top_photo_folder/$folder"

if [ $f_tz95 -eq 1 ]
then
    if [ $folder_tz95 -ne 0 ]
    then
        p_folder="$base_folder/tz95"
    else
        p_folder="$base_folder"
    fi
    params_tz95="$params $p_folder -d $d_tz95 --kml ../temp/photos_${folder}_tz95.kml"
    echo "$cmd $params_tz95"

    eval "$cmd $params_tz95"

    echo -e "\n===============\n"
fi


if [ $f_rx100 -eq 1 ]
then
    if [ $folder_rx100 -ne 0 ]
    then
        p_folder="$base_folder/rx100"
    else
        p_folder="$base_folder"
    fi
    params_rx100="$params $p_folder -d $d_rx100 --kml ../temp/photos_${folder}_rx100.kml"
    echo "$cmd $params_rx100"

    eval "$cmd $params_rx100"

    echo -e "\n===============\n"
fi


if [ $f_xs10 -eq 1 ]
then
    if [ $folder_xs10 -ne 0 ]
    then
        p_folder="$base_folder/xs10"
    else
        p_folder="$base_folder"
    fi
    params_xs10="$params $p_folder -d $d_xs10 --kml ../temp/photos_${folder}_xs10.kml"
    echo "$cmd $params_xs10"

    eval "$cmd $params_xs10"

    echo -e "\n===============\n"
fi
