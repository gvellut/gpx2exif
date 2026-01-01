export PYTHONPATH=`pwd`/..

top_photo_folder="/Volumes/CrucialX8/photos"
folder="20251226_semnoz"
gpx="/Users/guilhem/Library/CloudStorage/GoogleDrive-guilhem.vellut@gmail.com/My Drive/___gpx/20251226-123041.gpx"

d_tz95="-1h16m54s"
d_rx100="16:18:56-17:15:03"
d_xs20="-59m3s"

f_tz95=1
f_rx100=0
f_xs20=1

folder_tz95=1
folder_rx100=1
folder_xs20=1

tz="Europe/Paris"

update=1

cmd="uv run python"
params="-m gpx2exif.main image --tz $tz --clear --ignore-offset --update-time --kml_thumbnail_size 350 \"$gpx\""
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


if [ $f_xs20 -eq 1 ]
then
    if [ $folder_xs20 -ne 0 ]
    then
        p_folder="$base_folder/xs20"
    else
        p_folder="$base_folder"
    fi
    params_xs20="$params $p_folder -d $d_xs20 --kml ../temp/photos_${folder}_xs20.kml"
    echo "$cmd $params_xs20"

    eval "$cmd $params_xs20"

    echo -e "\n===============\n"
fi
